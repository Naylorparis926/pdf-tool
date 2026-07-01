import os
import uuid
import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from converters.pdf_to_word import convert_pdf_to_word
from converters.word_to_pdf import convert_word_to_pdf
from converters.compress import compress_pdf
from converters.cleanup import start_cleanup_scheduler

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
FILE_TTL_HOURS = 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_cleanup_scheduler(UPLOAD_DIR, PROCESSED_DIR, hours=FILE_TTL_HOURS)
    yield


app = FastAPI(title="PDF Tool", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")

    file_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{file_id}{ext}"
    with open(upload_path, "wb") as f:
        f.write(content)

    expires_at = datetime.datetime.now() + datetime.timedelta(hours=FILE_TTL_HOURS)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "extension": ext,
        "expires_at": expires_at.isoformat(),
    }


@app.post("/api/convert/{file_id}")
async def convert_file(file_id: str, target_format: str = Form(...)):
    ext = None
    path = None
    for e in ALLOWED_EXTENSIONS:
        p = UPLOAD_DIR / f"{file_id}{e}"
        if p.exists():
            ext = e
            path = p
            break

    if not path:
        raise HTTPException(404, "File not found or expired")

    if target_format == "docx" and ext == ".pdf":
        output_name = f"{file_id}_converted.docx"
        output_path = PROCESSED_DIR / output_name
        convert_pdf_to_word(str(path), str(output_path))
    elif target_format == "pdf" and ext == ".docx":
        output_name = f"{file_id}_converted.pdf"
        output_path = PROCESSED_DIR / output_name
        convert_word_to_pdf(str(path), str(output_path))
    else:
        raise HTTPException(400, f"Cannot convert from {ext} to {target_format}")

    expires_at = datetime.datetime.now() + datetime.timedelta(hours=FILE_TTL_HOURS)

    return {
        "file_id": output_name,
        "filename": f"converted.{target_format}",
        "download_url": f"/api/download/{output_name}",
        "expires_at": expires_at.isoformat(),
    }


@app.post("/api/compress/{file_id}")
async def compress_file(file_id: str, level: str = Form("balanced")):
    if level not in ("light", "balanced", "maximum"):
        raise HTTPException(400, "Invalid compression level")

    path = UPLOAD_DIR / f"{file_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "File not found or expired")

    output_name = f"{file_id}_compressed.pdf"
    output_path = PROCESSED_DIR / output_name

    result = compress_pdf(str(path), str(output_path), level)

    expires_at = datetime.datetime.now() + datetime.timedelta(hours=FILE_TTL_HOURS)

    return {
        "file_id": output_name,
        "filename": "compressed.pdf",
        "download_url": f"/api/download/{output_name}",
        "original_size": result["original_size"],
        "compressed_size": result["compressed_size"],
        "ratio": result["ratio"],
        "expires_at": expires_at.isoformat(),
    }


@app.get("/api/download/{file_name:path}")
async def download_file(file_name: str):
    path = PROCESSED_DIR / file_name
    if not path.exists():
        raise HTTPException(404, "File expired or not found")
    return FileResponse(str(path), filename=path.name)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

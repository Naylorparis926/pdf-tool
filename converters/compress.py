import os
import io
import fitz
from PIL import Image


def compress_pdf(input_path: str, output_path: str, level: str = "balanced") -> dict:
    configs = {
        "light":   {"quality": 85, "max_dim": 2000},
        "balanced":{"quality": 70, "max_dim": 1500},
        "maximum": {"quality": 50, "max_dim": 1000},
    }
    cfg = configs.get(level, configs["balanced"])

    orig_size = os.path.getsize(input_path)

    doc = fitz.open(input_path)

    for page_num in range(doc.page_count):
        page = doc[page_num]
        images = page.get_images(full=True)

        for img_info in images:
            xref = img_info[0]
            try:
                base = doc.extract_image(xref)
                ext = base["ext"]
                img_bytes = base["image"]

                pil_img = Image.open(io.BytesIO(img_bytes))

                if max(pil_img.size) > cfg["max_dim"]:
                    ratio = cfg["max_dim"] / max(pil_img.size)
                    pil_img = pil_img.resize(
                        (int(pil_img.width * ratio), int(pil_img.height * ratio)),
                        Image.LANCZOS,
                    )

                out = io.BytesIO()
                fmt = ext.upper()
                if fmt == "JPG":
                    fmt = "JPEG"

                if fmt in ("JPEG",):
                    if pil_img.mode in ("RGBA", "LA", "P"):
                        pil_img = pil_img.convert("RGB")
                    pil_img.save(out, "JPEG", quality=cfg["quality"], optimize=True)
                else:
                    if pil_img.mode == "P":
                        pil_img = pil_img.convert("RGBA")
                    pil_img.save(out, "PNG", optimize=True)
                out.seek(0)

                page.replace_image(xref, stream=out.read())
            except Exception:
                pass

    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()

    new_size = os.path.getsize(output_path)
    ratio = round((1 - new_size / orig_size) * 100, 1) if orig_size > 0 else 0

    return {"original_size": orig_size, "compressed_size": new_size, "ratio": ratio}

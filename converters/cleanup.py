import time
import threading
from pathlib import Path


def _cleanup_worker(upload_dir: Path, processed_dir: Path, ttl_seconds: int):
    while True:
        now = time.time()
        for d in (upload_dir, processed_dir):
            if d.exists():
                for f in d.iterdir():
                    if f.is_file():
                        try:
                            if now - f.stat().st_mtime > ttl_seconds:
                                f.unlink()
                        except (PermissionError, OSError):
                            pass
        time.sleep(300)


def start_cleanup_scheduler(upload_dir: Path, processed_dir: Path, hours: int = 1):
    ttl = hours * 3600
    t = threading.Thread(
        target=_cleanup_worker,
        args=(upload_dir, processed_dir, ttl),
        daemon=True,
    )
    t.start()

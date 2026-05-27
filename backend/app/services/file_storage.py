"""文件存储服务：按 SHA1 去重存储到磁盘 + DB。"""
from __future__ import annotations
import hashlib
import os
import shutil
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import File


def _hash_stream(stream) -> tuple[str, int]:
    """计算 stream 的 SHA1 + 字节数。stream 是 file-like。"""
    h = hashlib.sha1()
    size = 0
    while True:
        chunk = stream.read(1 << 20)
        if not chunk:
            break
        h.update(chunk)
        size += len(chunk)
    return h.hexdigest(), size


def _storage_path(sha1: str) -> Path:
    # 用前两位做二级目录，避免单目录文件过多
    return Path(settings.storage_dir) / "pdfs" / sha1[:2] / f"{sha1}.pdf"


def save_upload(db: Session, upload, *, mime: str = "application/pdf") -> File:
    """保存上传文件，去重存储。upload 是 FastAPI 的 UploadFile（同步版本读 .file）。

    返回 File 记录。同 sha1 已存在则复用。
    """
    upload.file.seek(0)
    sha1, size = _hash_stream(upload.file)

    existing = db.scalar(select(File).where(File.sha1 == sha1))
    if existing:
        return existing

    dest = _storage_path(sha1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    upload.file.seek(0)
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)

    # 算页数（PDF）
    page_count = None
    try:
        import fitz
        with fitz.open(dest) as doc:
            page_count = len(doc)
    except Exception:
        pass

    rec = File(
        sha1=sha1,
        path=str(dest),
        original_name=upload.filename or "",
        mime_type=mime,
        size_bytes=size,
        page_count=page_count,
    )
    db.add(rec)
    db.flush()
    return rec


def open_file_path(file: File) -> Path:
    return Path(file.path)


def probe_pdf_text(path: str | Path, *, sample_pages: int = 3) -> int:
    """快速探测 PDF 前几页能直抽多少个非空字符，用于判断是"文字 PDF"还是"扫描 PDF"。

    - 文字 PDF（电子版）：会有大量可抽取文字（通常 > 200 字符/页）
    - 扫描 PDF（盖章扫描）：直抽几乎没有文字（< 20 字符/页）
    返回前 sample_pages 页总字符数。
    """
    try:
        import fitz
        with fitz.open(path) as doc:
            n = min(sample_pages, len(doc))
            total = 0
            for i in range(n):
                t = doc[i].get_text("text") or ""
                total += len(t.strip())
            return total
    except Exception:
        return 0

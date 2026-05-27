"""File 模型：按 SHA1 去重存储的 PDF/其他文件。"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    sha1: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), default="application/pdf", nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

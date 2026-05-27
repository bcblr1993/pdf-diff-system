"""Comparison 模型：一次 PDF 对比任务。"""
from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import (
    String, DateTime, Integer, ForeignKey, Enum as SAEnum, JSON, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ComparisonStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class ReviewStatus(str, enum.Enum):
    not_started = "not_started"
    in_review = "in_review"
    completed = "completed"


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    orig_file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="RESTRICT"), nullable=False)
    scan_file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="RESTRICT"), nullable=False)

    status: Mapped[ComparisonStatus] = mapped_column(
        SAEnum(ComparisonStatus, name="comparison_status"),
        default=ComparisonStatus.pending,
        nullable=False,
        index=True,
    )
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_phase: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    # 对比设置（DPI/阈值等，未来开放给用户配置）
    settings_json: Mapped[dict | None] = mapped_column(JSON)
    # diff 汇总：{total, real, critical, replace, insert, delete, moved, handwritten, stamp_covered, footer}
    summary_json: Mapped[dict | None] = mapped_column(JSON)

    # 审核流
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status"),
        default=ReviewStatus.not_started,
        nullable=False,
        index=True,
    )
    review_completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    review_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # relationships
    orig_file = relationship("File", foreign_keys=[orig_file_id], lazy="joined")
    scan_file = relationship("File", foreign_keys=[scan_file_id], lazy="joined")
    diffs = relationship("Diff", back_populates="comparison", cascade="all, delete-orphan", lazy="select")

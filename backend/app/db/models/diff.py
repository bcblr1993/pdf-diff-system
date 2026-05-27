"""Diff 模型：一条差异条目。"""
from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import (
    String, DateTime, Integer, ForeignKey, Enum as SAEnum, JSON, Text, Boolean, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class DiffCategory(str, enum.Enum):
    replace = "replace"           # 修改（黄）
    delete = "delete"             # 删除（红）
    insert = "insert"             # 新增（绿）
    handwritten = "handwritten"   # 手写填空（绿）
    stamp_covered = "stamp_covered"  # 章遮挡（灰）
    moved = "moved"               # 位置移动（蓝）


class DiffSeverity(str, enum.Enum):
    critical = "critical"
    normal = "normal"
    info = "info"


class ReviewAction(str, enum.Enum):
    confirmed = "confirmed"  # 确认是问题
    ignored = "ignored"      # 忽略，不算问题


class Diff(Base):
    __tablename__ = "diffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparisons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    category: Mapped[DiffCategory] = mapped_column(
        SAEnum(DiffCategory, name="diff_category"), nullable=False, index=True
    )
    severity: Mapped[DiffSeverity] = mapped_column(
        SAEnum(DiffSeverity, name="diff_severity"), nullable=False, index=True
    )

    orig_page: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    scan_page: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    orig_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scan_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    orig_bbox: Mapped[list | None] = mapped_column(JSON)   # [x0,y0,x1,y1] pt
    scan_bbox: Mapped[list | None] = mapped_column(JSON)
    context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_footer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 审核字段
    review_action: Mapped[ReviewAction | None] = mapped_column(
        SAEnum(ReviewAction, name="diff_review_action")
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    comparison = relationship("Comparison", back_populates="diffs")

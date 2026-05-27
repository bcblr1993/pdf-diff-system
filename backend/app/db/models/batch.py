"""BatchJob 批量对比任务：一份原件 vs N 份扫描件。"""
from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class BatchStatus(str, enum.Enum):
    pending = "pending"      # 至少一个子任务还在排队/处理
    running = "running"
    done = "done"            # 全部子任务 done
    partial = "partial"      # 部分失败
    failed = "failed"        # 全部失败


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    orig_file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[BatchStatus] = mapped_column(
        SAEnum(BatchStatus, name="batch_status"),
        default=BatchStatus.pending, nullable=False, index=True,
    )
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    orig_file = relationship("File", lazy="joined")
    comparisons = relationship(
        "Comparison", back_populates="batch",
        cascade="all, delete-orphan", lazy="select",
        order_by="Comparison.id.asc()",
    )

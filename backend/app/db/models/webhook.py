"""Webhook 订阅模型。"""
from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Boolean, JSON, Enum as SAEnum, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class WebhookEvent(str, enum.Enum):
    comparison_done = "comparison.done"
    comparison_failed = "comparison.failed"
    batch_done = "batch.done"


class WebhookDeliveryStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)  # HMAC 签名密钥
    # 订阅的事件列表（如 ["comparison.done", "batch.done"]）
    events_json: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class WebhookDelivery(Base):
    """Webhook 投递日志。"""
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    webhook_id: Mapped[int] = mapped_column(
        ForeignKey("webhooks.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        SAEnum(WebhookDeliveryStatus, name="webhook_delivery_status"),
        default=WebhookDeliveryStatus.pending, nullable=False, index=True,
    )
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

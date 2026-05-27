"""Webhook Schema。"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from app.db.models import WebhookEvent, WebhookDeliveryStatus


class WebhookCreate(BaseModel):
    name: str = Field(default="", max_length=128)
    url: HttpUrl
    events: list[WebhookEvent] = Field(
        min_length=1,
        examples=[["comparison.done", "batch.done"]],
    )


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: HttpUrl | None = None
    events: list[WebhookEvent] | None = None
    is_active: bool | None = None


class WebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    url: str
    events_json: list[str]
    is_active: bool
    created_by: int | None
    created_at: datetime


class WebhookCreated(WebhookOut):
    secret: str = Field(description="HMAC 签名密钥（仅此次创建可见）")


class WebhookDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    webhook_id: int
    event: str
    status: WebhookDeliveryStatus
    response_status: int | None
    attempts: int
    error: str | None
    created_at: datetime
    completed_at: datetime | None

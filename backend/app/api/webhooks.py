"""管理 API：Webhooks（仅管理员）。"""
from __future__ import annotations
import secrets
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import Webhook, WebhookDelivery
from app.core.deps import AdminUser
from app.services.audit import log_action
from app.schemas.common import Page, Message
from app.schemas.webhook import (
    WebhookCreate, WebhookUpdate, WebhookOut, WebhookCreated, WebhookDeliveryOut,
)


router = APIRouter(prefix="/api/webhooks", tags=["Webhooks 管理"])


@router.post(
    "",
    response_model=WebhookCreated,
    summary="注册 Webhook（仅管理员）",
    description="完成 / 失败事件会 POST 到 url，HMAC-SHA256 签名在 `X-PdfDiff-Signature` Header。",
)
def create_webhook(
    body: WebhookCreate,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    secret = secrets.token_urlsafe(32)
    rec = Webhook(
        name=body.name,
        url=str(body.url),
        secret=secret,
        events_json=[e.value for e in body.events],
        is_active=True,
        created_by=admin.id,
    )
    db.add(rec)
    db.flush()
    log_action(db, user_id=admin.id, action="webhook.create",
               target_type="webhook", target_id=rec.id,
               payload={"url": str(body.url), "events": [e.value for e in body.events]})
    db.commit()
    db.refresh(rec)
    return WebhookCreated(
        id=rec.id, name=rec.name, url=rec.url, events_json=rec.events_json,
        is_active=rec.is_active, created_by=rec.created_by, created_at=rec.created_at,
        secret=secret,
    )


@router.get("", response_model=Page[WebhookOut], summary="Webhook 列表")
def list_webhooks(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
):
    total = db.scalar(select(sa_func.count(Webhook.id))) or 0
    items = db.scalars(
        select(Webhook).order_by(Webhook.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{wid}", response_model=WebhookOut, summary="更新 Webhook")
def update_webhook(
    wid: int,
    body: WebhookUpdate,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = db.get(Webhook, wid)
    if not rec:
        raise HTTPException(status_code=404, detail="Webhook 不存在")
    if body.name is not None:
        rec.name = body.name
    if body.url is not None:
        rec.url = str(body.url)
    if body.events is not None:
        rec.events_json = [e.value for e in body.events]
    if body.is_active is not None:
        rec.is_active = body.is_active
    log_action(db, user_id=admin.id, action="webhook.update",
               target_type="webhook", target_id=wid)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/{wid}", response_model=Message, summary="删除 Webhook")
def delete_webhook(
    wid: int,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = db.get(Webhook, wid)
    if not rec:
        raise HTTPException(status_code=404, detail="Webhook 不存在")
    log_action(db, user_id=admin.id, action="webhook.delete",
               target_type="webhook", target_id=wid)
    db.delete(rec)
    db.commit()
    return Message(message="已删除")


@router.get("/{wid}/deliveries", response_model=Page[WebhookDeliveryOut], summary="投递记录")
def list_deliveries(
    wid: int,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
):
    total = db.scalar(
        select(sa_func.count(WebhookDelivery.id)).where(WebhookDelivery.webhook_id == wid)
    ) or 0
    items = db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == wid)
        .order_by(WebhookDelivery.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(items=items, total=total, page=page, page_size=page_size)

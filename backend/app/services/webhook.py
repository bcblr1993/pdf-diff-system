"""Webhook 触发服务：异步推送 + HMAC-SHA256 签名 + 最多 3 次重试。"""
from __future__ import annotations
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.db.models import (
    Webhook, WebhookDelivery, WebhookDeliveryStatus,
)
from app.core.logging import get_logger


log = get_logger("webhook")

SIGNATURE_HEADER = "X-PdfDiff-Signature"
EVENT_HEADER = "X-PdfDiff-Event"
TIMESTAMP_HEADER = "X-PdfDiff-Timestamp"
DELIVERY_HEADER = "X-PdfDiff-Delivery"


def _sign(secret: str, ts: str, body: bytes) -> str:
    """HMAC-SHA256(secret, ts + '.' + body)，返回 hex。"""
    msg = ts.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def trigger_event(event: str, payload: dict) -> None:
    """触发某个事件。同步遍历订阅，对每个发起 HTTP POST（同步带超时）。

    Worker 调用，已在后台线程中，不阻塞 web。
    """
    with SessionLocal() as db:
        hooks = db.scalars(
            select(Webhook).where(Webhook.is_active.is_(True))
        ).all()
        targets = [h for h in hooks if event in (h.events_json or [])]
        if not targets:
            return
        log.info("触发 webhook", evt=event, count=len(targets))

        for hook in targets:
            _deliver(db, hook, event, payload)


def _deliver(db: Session, hook: Webhook, event: str, payload: dict) -> None:
    """单次投递，最多 3 次重试。"""
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ts = str(int(time.time()))
    sig = _sign(hook.secret, ts, body_bytes)

    delivery = WebhookDelivery(
        webhook_id=hook.id,
        event=event,
        payload_json=payload,
        status=WebhookDeliveryStatus.pending,
    )
    db.add(delivery)
    db.flush()

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        EVENT_HEADER: event,
        TIMESTAMP_HEADER: ts,
        SIGNATURE_HEADER: f"sha256={sig}",
        DELIVERY_HEADER: str(delivery.id),
        "User-Agent": "PdfDiff-Webhook/1.0",
    }

    last_err = None
    response_status = None
    response_body = None
    for attempt in range(1, 4):
        delivery.attempts = attempt
        try:
            r = httpx.post(hook.url, content=body_bytes, headers=headers, timeout=10.0)
            response_status = r.status_code
            response_body = (r.text or "")[:2000]
            if 200 <= r.status_code < 300:
                delivery.status = WebhookDeliveryStatus.success
                delivery.response_status = response_status
                delivery.response_body = response_body
                delivery.completed_at = datetime.now(timezone.utc)
                db.commit()
                log.info("webhook 成功", hook_id=hook.id, evt=event, attempt=attempt)
                return
            else:
                last_err = f"HTTP {r.status_code}: {response_body[:200]}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            log.warning("webhook 投递异常", hook_id=hook.id, evt=event,
                        attempt=attempt, error=last_err)
        # 指数退避
        time.sleep(2 ** (attempt - 1))

    delivery.status = WebhookDeliveryStatus.failed
    delivery.error = last_err
    delivery.response_status = response_status
    delivery.response_body = response_body
    delivery.completed_at = datetime.now(timezone.utc)
    db.commit()
    log.error("webhook 投递失败（已重试 3 次）", hook_id=hook.id, evt=event, error=last_err)

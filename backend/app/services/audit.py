"""审计日志服务。"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.db.models import AuditLog


def log_action(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    target_type: str = "",
    target_id: int | None = None,
    payload: dict | None = None,
    ip: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload_json=payload,
        ip=ip,
    )
    db.add(entry)
    return entry

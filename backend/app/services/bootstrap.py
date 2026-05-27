"""首次启动自检：表是否就绪、初始管理员是否需要创建。"""
from __future__ import annotations
from sqlalchemy import select
from app.db.base import SessionLocal
from app.db.models import User, UserRole
from app.core.config import settings
from app.core.security import hash_password
from app.core.logging import get_logger

log = get_logger("bootstrap")


def ensure_initial_admin() -> None:
    """如果库里一个 admin 都没有，且 .env 配了 INITIAL_ADMIN_*，则创建一个。"""
    if not (settings.initial_admin_username and settings.initial_admin_password):
        return
    with SessionLocal() as db:
        exists = db.scalar(
            select(User).where(User.role == UserRole.admin, User.is_active == True)  # noqa: E712
        )
        if exists:
            log.info("已存在管理员，跳过初始化", username=exists.username)
            return
        u = User(
            username=settings.initial_admin_username,
            password_hash=hash_password(settings.initial_admin_password),
            display_name=settings.initial_admin_name or settings.initial_admin_username,
            role=UserRole.admin,
        )
        db.add(u)
        db.commit()
        log.info("已创建初始管理员", username=u.username)

"""API Key 服务：生成、哈希、校验。"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import ApiKey


KEY_PREFIX = "pdfd_live_"


def generate_key() -> tuple[str, str, str]:
    """生成新 API Key。返回 (full_key, key_prefix, key_hash)。

    格式：pdfd_live_<8 字符随机前缀>_<32 字符随机正文>
    """
    p = secrets.token_urlsafe(6).replace("_", "").replace("-", "")[:8]
    body = secrets.token_urlsafe(24).replace("_", "").replace("-", "")[:32]
    full = f"{KEY_PREFIX}{p}_{body}"
    prefix = f"{KEY_PREFIX}{p}"
    return full, prefix, _hash(full)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_key(db: Session, presented: str) -> ApiKey | None:
    """校验调用方提供的 key，返回有效记录或 None。"""
    if not presented or not presented.startswith(KEY_PREFIX):
        return None
    h = _hash(presented)
    rec = db.scalar(select(ApiKey).where(ApiKey.key_hash == h))
    if not rec or not rec.is_active:
        return None
    if rec.expires_at and rec.expires_at < datetime.now(timezone.utc):
        return None
    return rec


def touch_usage(db: Session, key: ApiKey) -> None:
    """记一次成功调用。"""
    key.last_used_at = datetime.now(timezone.utc)
    key.call_count = (key.call_count or 0) + 1

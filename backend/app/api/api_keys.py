"""管理 API：API Keys（仅管理员）。"""
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import ApiKey
from app.core.deps import AdminUser
from app.services import api_key as ak_service
from app.services.audit import log_action
from app.schemas.common import Page, Message
from app.schemas.api_key import ApiKeyCreate, ApiKeyOut, ApiKeyCreated


router = APIRouter(prefix="/api/api-keys", tags=["API Keys 管理"])


@router.post(
    "",
    response_model=ApiKeyCreated,
    summary="创建 API Key（仅管理员）",
    description="**完整 Key 只在此次响应里返回一次**，妥善保存。后续 DB 只存哈希。",
)
def create_api_key(
    body: ApiKeyCreate,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    full, prefix, h = ak_service.generate_key()
    rec = ApiKey(
        name=body.name,
        key_hash=h,
        key_prefix=prefix,
        created_by=admin.id,
        expires_at=body.expires_at,
        is_active=True,
    )
    db.add(rec)
    db.flush()
    log_action(db, user_id=admin.id, action="api_key.create",
               target_type="api_key", target_id=rec.id,
               payload={"name": body.name})
    db.commit()
    db.refresh(rec)
    return ApiKeyCreated(
        id=rec.id, name=rec.name, key_prefix=rec.key_prefix,
        is_active=rec.is_active, expires_at=rec.expires_at,
        last_used_at=rec.last_used_at, call_count=rec.call_count,
        created_by=rec.created_by, created_at=rec.created_at,
        full_key=full,
    )


@router.get("", response_model=Page[ApiKeyOut], summary="API Key 列表")
def list_api_keys(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
):
    total = db.scalar(select(sa_func.count(ApiKey.id))) or 0
    items = db.scalars(
        select(ApiKey).order_by(ApiKey.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{kid}/disable", response_model=Message, summary="吊销 API Key")
def disable_api_key(
    kid: int,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = db.get(ApiKey, kid)
    if not rec:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    rec.is_active = False
    log_action(db, user_id=admin.id, action="api_key.disable",
               target_type="api_key", target_id=kid)
    db.commit()
    return Message(message="已吊销")


@router.delete("/{kid}", response_model=Message, summary="删除 API Key")
def delete_api_key(
    kid: int,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = db.get(ApiKey, kid)
    if not rec:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    log_action(db, user_id=admin.id, action="api_key.delete",
               target_type="api_key", target_id=kid)
    db.delete(rec)
    db.commit()
    return Message(message="已删除")

"""认证路由。"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import User, UserRole
from app.core.security import verify_password, create_access_token, hash_password
from app.core.deps import CurrentUser, AdminUser
from app.schemas.auth import LoginRequest, TokenResponse, UserOut, UserCreate
from app.schemas.common import Page, Message


router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description="用用户名密码换取 JWT。Swagger UI 上点 Authorize 输入 token 即可调用其他接口。",
)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(user.id, extra={"role": user.role.value})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut, summary="当前登录用户信息")
def me(user: CurrentUser):
    return user


# ── 用户管理（仅管理员） ────────────────────────────────
users_router = APIRouter(prefix="/api/users", tags=["用户管理"])


@users_router.post("", response_model=UserOut, summary="创建用户（仅管理员）")
def create_user(
    body: UserCreate,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=400, detail="用户名已存在")
    u = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        role=body.role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@users_router.get("", response_model=Page[UserOut], summary="用户列表（仅管理员）")
def list_users(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
):
    q = select(User).order_by(User.id.desc())
    total = db.scalar(select(User.id).order_by(User.id.desc()).limit(1).offset(0))
    from sqlalchemy import func as sa_func
    total = db.scalar(select(sa_func.count(User.id)))
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total or 0, page=page, page_size=page_size)


@users_router.patch("/{user_id}/disable", response_model=Message, summary="禁用用户")
def disable_user(
    user_id: int,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    u.is_active = False
    db.commit()
    return Message(message="已禁用")

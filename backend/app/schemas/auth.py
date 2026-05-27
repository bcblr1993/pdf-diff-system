"""认证相关 Schema。"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.db.models import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, examples=["admin"])
    password: str = Field(min_length=1, max_length=128, examples=["admin123"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=128)
    role: UserRole = UserRole.reviewer

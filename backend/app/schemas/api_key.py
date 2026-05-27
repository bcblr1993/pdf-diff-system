"""API Key Schema。"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, examples=["合同系统集成"])
    expires_at: datetime | None = Field(default=None, description="过期时间（可选）")


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    call_count: int
    created_by: int | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    full_key: str = Field(description="完整 Key（仅此次创建可见，请妥善保存）")

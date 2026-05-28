"""通用 Pydantic Schema。"""
from __future__ import annotations
from typing import Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(default=1, ge=1)
    # 响应限制放宽到 2000：列表 API 默认 200，但详情页 diffs 一次性拿全部
    page_size: int = Field(default=20, ge=1, le=2000)


class Message(BaseModel):
    message: str

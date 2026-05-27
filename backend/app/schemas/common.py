"""通用 Pydantic Schema。"""
from __future__ import annotations
from typing import Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class Message(BaseModel):
    message: str

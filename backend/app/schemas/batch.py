"""Batch Schema。"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.db.models import BatchStatus
from app.schemas.comparison import ComparisonBrief, FileBrief


class BatchBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    created_by: int | None
    status: BatchStatus
    total: int
    completed: int
    failed: int
    created_at: datetime
    completed_at: datetime | None


class BatchDetail(BatchBrief):
    orig_file: FileBrief
    comparisons: list[ComparisonBrief] = []


class BatchCreated(BaseModel):
    id: int
    total: int
    comparison_ids: list[int]
    message: str = "已创建批量任务，所有子任务已入队"

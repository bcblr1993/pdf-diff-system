"""Comparison Schema。"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.db.models import ComparisonStatus, ReviewStatus


class FileBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sha1: str
    original_name: str
    page_count: int | None
    size_bytes: int


class ComparisonBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    created_by: int | None
    status: ComparisonStatus
    review_status: ReviewStatus
    progress_pct: int
    progress_phase: str
    summary_json: dict | None
    created_at: datetime
    completed_at: datetime | None


class ComparisonDetail(ComparisonBrief):
    orig_file: FileBrief
    scan_file: FileBrief
    settings_json: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    review_completed_by: int | None = None
    review_completed_at: datetime | None = None


class ComparisonCreated(BaseModel):
    id: int
    status: ComparisonStatus
    message: str = "已创建并入队，可通过 WebSocket /ws/comparisons/{id}/progress 监听进度"

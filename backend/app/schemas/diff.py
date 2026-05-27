"""Diff Schema。"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.db.models import DiffCategory, DiffSeverity, ReviewAction


class DiffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    seq_no: int
    category: DiffCategory
    severity: DiffSeverity
    orig_page: int
    scan_page: int
    orig_text: str
    scan_text: str
    orig_bbox: list[float] | None
    scan_bbox: list[float] | None
    context: str
    is_footer: bool
    review_action: ReviewAction | None
    review_note: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None


class DiffReviewUpdate(BaseModel):
    review_action: ReviewAction | None  # None 表示撤销审核
    review_note: str | None = None

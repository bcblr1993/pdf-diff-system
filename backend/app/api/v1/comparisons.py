"""外部 API v1：对比任务（API Key 鉴权）。"""
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FFile, Form, Query, status
from sqlalchemy import select, func as sa_func, and_
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import (
    Comparison, ComparisonStatus, Diff, DiffCategory, DiffSeverity,
)
from app.services import file_storage
from app.schemas.common import Page
from app.schemas.comparison import ComparisonBrief, ComparisonDetail, ComparisonCreated
from app.schemas.diff import DiffOut
from app.api.v1.deps import CurrentApiKey


router = APIRouter(prefix="/api/v1", tags=["外部 API v1"])


@router.post(
    "/comparisons",
    response_model=ComparisonCreated,
    status_code=status.HTTP_201_CREATED,
    summary="[外部] 创建对比任务",
    description=(
        "**外部 API**，使用 `X-API-Key` Header 鉴权。\n\n"
        "上传原件与扫描件 PDF，异步处理。通过返回的 id 轮询 `GET /api/v1/comparisons/{id}` "
        "查状态，或在 Webhook 中接收 `comparison.done` 事件。"
    ),
)
def v1_create_comparison(
    key: CurrentApiKey,
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str, Form()] = "",
    orig: UploadFile = FFile(..., description="原件 PDF"),
    scan: UploadFile = FFile(..., description="扫描件 PDF"),
    dpi: Annotated[int, Form()] = 200,
):
    if orig.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="原件必须是 PDF")
    if scan.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="扫描件必须是 PDF")

    orig_f = file_storage.save_upload(db, orig)
    scan_f = file_storage.save_upload(db, scan)

    orig_chars = file_storage.probe_pdf_text(orig_f.path)
    scan_chars = file_storage.probe_pdf_text(scan_f.path)
    if orig_chars < 50 and scan_chars > 500:
        raise HTTPException(
            status_code=400,
            detail=f"两份 PDF 似乎放反了：原件位置仅 {orig_chars} 字符，扫描件位置 {scan_chars} 字符",
        )

    cmp = Comparison(
        title=title or f"[API] {orig_f.original_name} vs {scan_f.original_name}",
        created_by=key.created_by,
        orig_file_id=orig_f.id,
        scan_file_id=scan_f.id,
        status=ComparisonStatus.pending,
        settings_json={"dpi": dpi, "source": "api", "api_key_id": key.id},
    )
    db.add(cmp)
    db.flush()
    db.commit()
    db.refresh(cmp)

    from app.workers.queue import enqueue_comparison
    enqueue_comparison(cmp.id)

    return ComparisonCreated(id=cmp.id, status=cmp.status)


@router.get(
    "/comparisons",
    response_model=Page[ComparisonBrief],
    summary="[外部] 对比任务列表",
)
def v1_list_comparisons(
    _key: CurrentApiKey,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: ComparisonStatus | None = Query(None, alias="status"),
):
    q = select(Comparison).order_by(Comparison.id.desc())
    cq = select(sa_func.count(Comparison.id))
    if status_filter:
        q = q.where(Comparison.status == status_filter)
        cq = cq.where(Comparison.status == status_filter)
    total = db.scalar(cq) or 0
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/comparisons/{cid}",
    response_model=ComparisonDetail,
    summary="[外部] 对比任务详情 + 摘要",
)
def v1_get_comparison(
    cid: int,
    _key: CurrentApiKey,
    db: Annotated[Session, Depends(get_db)],
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    return cmp


@router.get(
    "/comparisons/{cid}/diffs",
    response_model=Page[DiffOut],
    summary="[外部] 拉取差异列表",
)
def v1_list_diffs(
    cid: int,
    _key: CurrentApiKey,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    include_noise: bool = Query(False),
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    q = select(Diff).where(Diff.comparison_id == cid).order_by(Diff.seq_no.asc())
    cq = select(sa_func.count(Diff.id)).where(Diff.comparison_id == cid)
    if not include_noise:
        cond = and_(
            Diff.category != DiffCategory.moved,
            Diff.severity != DiffSeverity.info,
            Diff.is_footer.is_(False),
        )
        q = q.where(cond)
        cq = cq.where(cond)
    total = db.scalar(cq) or 0
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/health", summary="[外部] 健康检查（带 API Key 校验）")
def v1_health(key: CurrentApiKey):
    return {"status": "ok", "key_name": key.name, "key_prefix": key.key_prefix}

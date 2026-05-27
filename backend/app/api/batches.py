"""批量对比任务 API：1 份原件 vs N 份扫描件。"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FFile, Form, Query, status
from sqlalchemy import select, func as sa_func, case
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import BatchJob, BatchStatus, Comparison, ComparisonStatus
from app.core.deps import CurrentUser
from app.services import file_storage
from app.services.audit import log_action
from app.schemas.common import Page, Message
from app.schemas.batch import BatchBrief, BatchDetail, BatchCreated


router = APIRouter(prefix="/api/batches", tags=["批量对比"])


@router.post(
    "",
    response_model=BatchCreated,
    status_code=status.HTTP_201_CREATED,
    summary="创建批量对比任务",
    description=(
        "上传**一份原件** + **多份扫描件**，系统为每份扫描件创建一个独立的对比任务，"
        "结果归属到同一个批量任务下。原件 SHA1 相同时自动共享 OCR 缓存。"
    ),
)
def create_batch(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str, Form(description="批量任务标题")] = "",
    orig: UploadFile = FFile(..., description="原件 PDF（电子矢量版，1 份）"),
    scans: list[UploadFile] = FFile(..., description="扫描件 PDF（盖章版，多份）"),
    dpi: Annotated[int, Form(description="OCR 渲染 DPI")] = 200,
):
    if not scans:
        raise HTTPException(status_code=400, detail="至少上传 1 份扫描件")
    if len(scans) > 50:
        raise HTTPException(status_code=400, detail="单次批量最多 50 份扫描件")

    orig_f = file_storage.save_upload(db, orig)
    # 原件防误传检测
    orig_chars = file_storage.probe_pdf_text(orig_f.path)
    if orig_chars < 50:
        raise HTTPException(
            status_code=400,
            detail=f"原件似乎是图像 PDF（前 3 页仅 {orig_chars} 字符），应上传文字可复制的电子版。"
        )

    batch = BatchJob(
        title=title or f"{orig_f.original_name} → {len(scans)} 份扫描件",
        created_by=user.id,
        orig_file_id=orig_f.id,
        total=len(scans),
        status=BatchStatus.pending,
    )
    db.add(batch)
    db.flush()  # 拿 batch.id

    comparison_ids: list[int] = []
    from app.workers.queue import enqueue_comparison

    for i, scan in enumerate(scans, start=1):
        scan_f = file_storage.save_upload(db, scan)
        cmp = Comparison(
            title=f"{batch.title} #{i} - {scan_f.original_name}",
            created_by=user.id,
            batch_id=batch.id,
            orig_file_id=orig_f.id,
            scan_file_id=scan_f.id,
            status=ComparisonStatus.pending,
            settings_json={"dpi": dpi},
        )
        db.add(cmp)
        db.flush()
        comparison_ids.append(cmp.id)

    log_action(
        db, user_id=user.id, action="batch.create",
        target_type="batch", target_id=batch.id,
        payload={"title": batch.title, "scan_count": len(scans), "dpi": dpi},
    )
    db.commit()

    # 入队（事务外避免锁库）
    for cid in comparison_ids:
        enqueue_comparison(cid)

    return BatchCreated(id=batch.id, total=len(scans), comparison_ids=comparison_ids)


@router.get("", response_model=Page[BatchBrief], summary="批量任务列表")
def list_batches(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: BatchStatus | None = Query(None, alias="status"),
    mine_only: bool = Query(False),
):
    # 先把每个 batch 的实时统计算出来，更新到记录里再查
    _refresh_batches(db)

    q = select(BatchJob).order_by(BatchJob.id.desc())
    cq = select(sa_func.count(BatchJob.id))
    if status_filter:
        q = q.where(BatchJob.status == status_filter)
        cq = cq.where(BatchJob.status == status_filter)
    if mine_only:
        q = q.where(BatchJob.created_by == user.id)
        cq = cq.where(BatchJob.created_by == user.id)
    total = db.scalar(cq) or 0
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{bid}", response_model=BatchDetail, summary="批量任务详情")
def get_batch(
    bid: int,
    _user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    _refresh_batch(db, bid)
    batch = db.get(BatchJob, bid)
    if not batch:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return batch


@router.delete("/{bid}", response_model=Message, summary="删除批量任务（级联删子任务）")
def delete_batch(
    bid: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    batch = db.get(BatchJob, bid)
    if not batch:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    log_action(db, user_id=user.id, action="batch.delete",
               target_type="batch", target_id=bid)
    db.delete(batch)
    db.commit()
    return Message(message="已删除")


# ─────── 内部：刷新 batch 状态汇总 ───────

def _refresh_batches(db: Session) -> None:
    """对所有非终态的 batch 跑一次状态汇总。"""
    ids = db.scalars(
        select(BatchJob.id).where(
            BatchJob.status.in_([BatchStatus.pending, BatchStatus.running])
        )
    ).all()
    for bid in ids:
        _refresh_batch(db, bid)


def _refresh_batch(db: Session, bid: int) -> None:
    batch = db.get(BatchJob, bid)
    if not batch:
        return
    # 实时统计子任务状态
    counts = db.execute(
        select(
            sa_func.count().label("total"),
            sa_func.sum(case((Comparison.status == ComparisonStatus.done, 1), else_=0)).label("done"),
            sa_func.sum(case((Comparison.status == ComparisonStatus.failed, 1), else_=0)).label("failed"),
            sa_func.sum(case((Comparison.status == ComparisonStatus.running, 1), else_=0)).label("running"),
        ).where(Comparison.batch_id == bid)
    ).one()
    total = counts.total or 0
    done = int(counts.done or 0)
    failed = int(counts.failed or 0)
    running = int(counts.running or 0)

    if total == 0:
        new_status = BatchStatus.pending
    elif done + failed == total:
        if failed == 0:
            new_status = BatchStatus.done
        elif done == 0:
            new_status = BatchStatus.failed
        else:
            new_status = BatchStatus.partial
    elif running > 0 or done > 0 or failed > 0:
        new_status = BatchStatus.running
    else:
        new_status = BatchStatus.pending

    changed = (
        batch.total != total or batch.completed != done
        or batch.failed != failed or batch.status != new_status
    )
    if changed:
        batch.total = total
        batch.completed = done
        batch.failed = failed
        old_status = batch.status
        batch.status = new_status
        if new_status in (BatchStatus.done, BatchStatus.partial, BatchStatus.failed) \
                and batch.completed_at is None:
            batch.completed_at = datetime.now(timezone.utc)
        if changed:
            db.commit()

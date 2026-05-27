"""差异条目 API：列表、审核标记。"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func, and_
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import (
    Comparison, Diff, DiffCategory, DiffSeverity, ReviewAction,
    ReviewStatus,
)
from app.core.deps import CurrentUser
from app.services.audit import log_action
from app.schemas.common import Page, Message
from app.schemas.diff import DiffOut, DiffReviewUpdate


router = APIRouter(tags=["差异"])


@router.get(
    "/api/comparisons/{cid}/diffs",
    response_model=Page[DiffOut],
    summary="获取对比任务的差异列表",
    description="支持按类别、严重度、是否已审核筛选。默认按序号正序。",
)
def list_diffs(
    cid: int,
    _user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    category: list[DiffCategory] | None = Query(None, description="按类别筛选，可多选"),
    severity: list[DiffSeverity] | None = Query(None, description="按严重度筛选，可多选"),
    reviewed: bool | None = Query(None, description="true=已审核 / false=未审核 / null=不筛选"),
    include_noise: bool = Query(
        False, description="是否包含 moved/footer/info 等噪声（默认排除）"
    ),
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")

    q = select(Diff).where(Diff.comparison_id == cid).order_by(Diff.seq_no.asc())
    cq = select(sa_func.count(Diff.id)).where(Diff.comparison_id == cid)
    if category:
        q = q.where(Diff.category.in_(category))
        cq = cq.where(Diff.category.in_(category))
    if severity:
        q = q.where(Diff.severity.in_(severity))
        cq = cq.where(Diff.severity.in_(severity))
    if reviewed is True:
        q = q.where(Diff.review_action.is_not(None))
        cq = cq.where(Diff.review_action.is_not(None))
    elif reviewed is False:
        q = q.where(Diff.review_action.is_(None))
        cq = cq.where(Diff.review_action.is_(None))
    if not include_noise:
        q = q.where(and_(
            Diff.category != DiffCategory.moved,
            Diff.severity != DiffSeverity.info,
            Diff.is_footer.is_(False),
        ))
        cq = cq.where(and_(
            Diff.category != DiffCategory.moved,
            Diff.severity != DiffSeverity.info,
            Diff.is_footer.is_(False),
        ))
    total = db.scalar(cq) or 0
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.patch(
    "/api/diffs/{did}",
    response_model=DiffOut,
    summary="更新差异审核状态",
    description="设置 confirmed/ignored；传 null 撤销。会自动把对比任务的 review_status 切换为 in_review。",
)
def update_diff_review(
    did: int,
    body: DiffReviewUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    d = db.get(Diff, did)
    if not d:
        raise HTTPException(status_code=404, detail="差异不存在")

    d.review_action = body.review_action
    d.review_note = body.review_note
    if body.review_action is None:
        d.reviewed_by = None
        d.reviewed_at = None
    else:
        d.reviewed_by = user.id
        d.reviewed_at = datetime.now(timezone.utc)

    cmp = db.get(Comparison, d.comparison_id)
    if cmp and cmp.review_status == ReviewStatus.not_started and body.review_action is not None:
        cmp.review_status = ReviewStatus.in_review

    log_action(db, user_id=user.id, action="diff.review",
               target_type="diff", target_id=did,
               payload={"action": body.review_action.value if body.review_action else None})
    db.commit()
    db.refresh(d)
    return d


@router.post(
    "/api/comparisons/{cid}/review/complete",
    response_model=Message,
    summary="标记审核完成",
    description="所有未审核条目按 ignored 处理，整个任务进入 completed 状态。",
)
def complete_review(
    cid: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    if cmp.status.value != "done":
        raise HTTPException(status_code=400, detail="对比未完成，不能进入审核完成态")

    # 未审核条目默认设为 ignored
    db.query(Diff).filter(
        Diff.comparison_id == cid,
        Diff.review_action.is_(None),
    ).update({
        Diff.review_action: ReviewAction.ignored,
        Diff.reviewed_by: user.id,
        Diff.reviewed_at: datetime.now(timezone.utc),
    })

    cmp.review_status = ReviewStatus.completed
    cmp.review_completed_by = user.id
    cmp.review_completed_at = datetime.now(timezone.utc)

    log_action(db, user_id=user.id, action="comparison.review_complete",
               target_type="comparison", target_id=cid)
    db.commit()
    return Message(message="审核已完成")

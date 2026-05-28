"""对比任务 API。"""
from __future__ import annotations
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FFile, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func as sa_func
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import Comparison, ComparisonStatus, ReviewStatus, File
from app.core.deps import CurrentUser
from app.services import file_storage
from app.services.audit import log_action
from app.schemas.common import Page, Message
from app.schemas.comparison import ComparisonBrief, ComparisonDetail, ComparisonCreated


router = APIRouter(prefix="/api/comparisons", tags=["对比任务"])


@router.post(
    "",
    response_model=ComparisonCreated,
    status_code=status.HTTP_201_CREATED,
    summary="创建对比任务",
    description=(
        "上传**原件** PDF（电子矢量版）和**扫描件** PDF（盖章扫描版），系统异步处理。\n\n"
        "返回 `id` 后，前端可通过 WebSocket `/ws/comparisons/{id}/progress` 监听实时进度，"
        "或轮询 GET `/api/comparisons/{id}`。"
    ),
)
def create_comparison(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str, Form(description="任务标题，便于识别")] = "",
    orig: UploadFile = FFile(..., description="原件 PDF"),
    scan: UploadFile = FFile(..., description="扫描件 PDF"),
    dpi: Annotated[int, Form(description="OCR 渲染 DPI（默认 200，提高可至 300）")] = 200,
):
    if not orig.filename or not scan.filename:
        raise HTTPException(status_code=400, detail="缺少文件")

    def _check_ext(filename: str, label: str):
        name = (filename or "").lower()
        if not (name.endswith(".pdf") or name.endswith(".docx")):
            raise HTTPException(
                status_code=400,
                detail=f"{label}必须是 PDF 或 Word 文档（.pdf / .docx），收到：{filename}"
            )

    _check_ext(orig.filename, "原件")
    _check_ext(scan.filename, "扫描件")

    orig_f = file_storage.save_upload(db, orig)
    scan_f = file_storage.save_upload(db, scan)

    # 防误传检测：仅在两份都是 PDF 时检查（Word 文件直接抽文本无需此检测）
    if file_storage.is_pdf(orig_f) and file_storage.is_pdf(scan_f):
        orig_chars = file_storage.probe_pdf_text(orig_f.path)
        scan_chars = file_storage.probe_pdf_text(scan_f.path)
        if orig_chars < 50 and scan_chars > 500:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"两份 PDF 似乎放反了：原件位置上传的是图像 PDF（前 3 页仅 {orig_chars} 字符），"
                    f"扫描件位置上传的是文字 PDF（前 3 页 {scan_chars} 字符）。"
                    "请把电子矢量版（文字可复制）放在「原件」，盖章扫描版放在「扫描件」。"
                ),
            )

    cmp = Comparison(
        title=title or f"{orig_f.original_name} vs {scan_f.original_name}",
        created_by=user.id,
        orig_file_id=orig_f.id,
        scan_file_id=scan_f.id,
        status=ComparisonStatus.pending,
        settings_json={"dpi": dpi},
    )
    db.add(cmp)
    db.flush()

    log_action(db, user_id=user.id, action="comparison.create",
               target_type="comparison", target_id=cmp.id,
               payload={"title": cmp.title, "dpi": dpi})
    db.commit()
    db.refresh(cmp)

    # 入队
    from app.workers.queue import enqueue_comparison
    enqueue_comparison(cmp.id)

    return ComparisonCreated(id=cmp.id, status=cmp.status)


@router.get("", response_model=Page[ComparisonBrief], summary="对比任务列表")
def list_comparisons(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: ComparisonStatus | None = Query(None, alias="status"),
    review_status: ReviewStatus | None = None,
    mine_only: bool = Query(False, description="仅查看我创建的"),
):
    q = select(Comparison).order_by(Comparison.id.desc())
    cq = select(sa_func.count(Comparison.id))
    if status_filter:
        q = q.where(Comparison.status == status_filter)
        cq = cq.where(Comparison.status == status_filter)
    if review_status:
        q = q.where(Comparison.review_status == review_status)
        cq = cq.where(Comparison.review_status == review_status)
    if mine_only:
        q = q.where(Comparison.created_by == user.id)
        cq = cq.where(Comparison.created_by == user.id)
    total = db.scalar(cq) or 0
    items = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{cid}", response_model=ComparisonDetail, summary="对比任务详情")
def get_comparison(
    cid: int,
    _user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    return cmp


@router.delete("/{cid}", response_model=Message, summary="删除对比任务")
def delete_comparison(
    cid: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    log_action(db, user_id=user.id, action="comparison.delete",
               target_type="comparison", target_id=cid)
    db.delete(cmp)
    db.commit()
    return Message(message="已删除")


def _serve_file(file_rec):
    p = Path(file_rec.path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="文件已丢失")
    return FileResponse(p, media_type=file_rec.mime_type, filename=file_rec.original_name or p.name)


@router.get("/{cid}/orig.pdf", summary="下载原件（PDF 或 Word）")
def download_orig(cid: int, _user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _serve_file(cmp.orig_file)


@router.get("/{cid}/scan.pdf", summary="下载扫描件（PDF 或 Word）")
def download_scan(cid: int, _user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _serve_file(cmp.scan_file)


@router.get("/{cid}/orig/text.json", summary="获取原件 Word 文本（按段落）")
def download_orig_word_text(cid: int, _user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    """Word 视图组件用：直接拿段落文本数组，避免前端解析 docx。"""
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not file_storage.is_word(cmp.orig_file):
        raise HTTPException(status_code=400, detail="原件不是 Word 文档")
    from pipeline.word import extract_docx
    pages = extract_docx(cmp.orig_file.path)
    lines = [ln.text for ln in pages[0].lines]
    return {"paragraphs": lines}


@router.get("/{cid}/scan/text.json", summary="获取扫描件 Word 文本（按段落）")
def download_scan_word_text(cid: int, _user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not file_storage.is_word(cmp.scan_file):
        raise HTTPException(status_code=400, detail="扫描件不是 Word 文档")
    from pipeline.word import extract_docx
    pages = extract_docx(cmp.scan_file.path)
    lines = [ln.text for ln in pages[0].lines]
    return {"paragraphs": lines}

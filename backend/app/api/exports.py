"""导出审核报告：Excel / HTML / PDF。"""
from __future__ import annotations
import re
from typing import Annotated
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import Comparison
from app.core.deps import CurrentUser
from app.services.audit import log_action
from app.exporters.xlsx import export_xlsx
from app.exporters.html_report import export_html
from app.exporters.pdf_report import export_pdf


router = APIRouter(tags=["导出"])


def _content_disposition(filename: str) -> str:
    """生成同时兼容老浏览器和中文文件名的 Content-Disposition。

    HTTP header 只能是 latin-1，所以 filename= 必须纯 ASCII；中文走 filename*=UTF-8''。
    """
    # 注意：Python \w 默认匹配 Unicode（含中文），要显式限定 ASCII
    ascii_safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "report"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_safe}\"; filename*=UTF-8''{encoded}"


def _safe_title(cmp: Comparison) -> str:
    raw = cmp.title or f"comparison-{cmp.id}"
    return re.sub(r"\s+", "-", raw.strip())[:80]


@router.get(
    "/api/comparisons/{cid}/export.xlsx",
    summary="导出 Excel 审核报告",
    description="3 个 sheet：摘要 / 全部差异清单 / 关键差异清单。",
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}},
)
def export_excel(
    cid: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    if cmp.status.value != "done":
        raise HTTPException(status_code=400, detail="对比未完成，无法导出")

    content = export_xlsx(db, cid)
    log_action(db, user_id=user.id, action="comparison.export",
               target_type="comparison", target_id=cid,
               payload={"format": "xlsx"})
    db.commit()

    fname = f"{_safe_title(cmp)}-审核报告.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": _content_disposition(fname)},
    )


@router.get(
    "/api/comparisons/{cid}/export.html",
    summary="导出 HTML 快照（含 PDF 截图高亮）",
    description="独立 HTML，内联 base64 页图，可邮件发送 / 单文件归档。",
)
def export_html_report(
    cid: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    include_noise: bool = Query(False, description="是否包含 moved/footer/info 等噪声"),
    dpi: int = Query(100, ge=72, le=200, description="页图 DPI，越高越清晰但文件越大"),
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    if cmp.status.value != "done":
        raise HTTPException(status_code=400, detail="对比未完成，无法导出")

    content = export_html(db, cid, dpi=dpi, include_noise=include_noise)
    log_action(db, user_id=user.id, action="comparison.export",
               target_type="comparison", target_id=cid,
               payload={"format": "html", "include_noise": include_noise})
    db.commit()

    fname = f"{_safe_title(cmp)}-审核报告.html"
    return Response(
        content=content,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(fname)},
    )


@router.get(
    "/api/comparisons/{cid}/export.pdf",
    summary="导出 PDF 审核报告",
    description="封面 + 摘要 + 关键差异 + 全部差异表，可直接归档/打印。",
)
def export_pdf_report(
    cid: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    cmp = db.get(Comparison, cid)
    if not cmp:
        raise HTTPException(status_code=404, detail="任务不存在")
    if cmp.status.value != "done":
        raise HTTPException(status_code=400, detail="对比未完成，无法导出")

    content = export_pdf(db, cid)
    log_action(db, user_id=user.id, action="comparison.export",
               target_type="comparison", target_id=cid,
               payload={"format": "pdf"})
    db.commit()

    fname = f"{_safe_title(cmp)}-审核报告.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(fname)},
    )

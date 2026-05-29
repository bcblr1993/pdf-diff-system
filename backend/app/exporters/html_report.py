"""HTML 快照导出：双 PDF 渲染 + 高亮 + 审核结论。

输出独立 HTML（PDF 页图 base64 内联），可单文件发邮件/归档。
"""
from __future__ import annotations
import base64
import html
import io
from datetime import datetime
import fitz
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Comparison, Diff, DiffCategory, DiffSeverity, ReviewAction, User


CATEGORY_LABEL = {
    "replace": "修改", "delete": "删除", "insert": "新增",
    "handwritten": "手写填空", "stamp_covered": "章遮挡", "moved": "位置移动",
}

CATEGORY_COLOR = {
    "replace": "rgba(250, 204, 21, 0.55)",
    "delete": "rgba(239, 68, 68, 0.45)",
    "insert": "rgba(34, 197, 94, 0.50)",
    "handwritten": "rgba(34, 197, 94, 0.50)",
    "stamp_covered": "rgba(180, 180, 180, 0.45)",
    "moved": "rgba(135, 180, 255, 0.35)",
}

NOISE_CATEGORIES = {"moved"}


def export_html(db: Session, comparison_id: int, *, dpi: int = 100, include_noise: bool = False) -> bytes:
    cmp = db.get(Comparison, comparison_id)
    if not cmp:
        raise ValueError("Comparison 不存在")

    diffs = db.scalars(
        select(Diff).where(Diff.comparison_id == comparison_id).order_by(Diff.seq_no.asc())
    ).all()

    if not include_noise:
        diffs = [
            d for d in diffs
            if d.category.value not in NOISE_CATEGORIES
            and d.severity.value != "info"
            and not d.is_footer
        ]

    reviewer_ids = {d.reviewed_by for d in diffs if d.reviewed_by}
    reviewer_map = {}
    if reviewer_ids:
        users = db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()
        reviewer_map = {u.id: u.display_name or u.username for u in users}

    # 渲染所有用到的页（orig + scan 都要）
    orig_pages_needed = sorted({d.orig_page for d in diffs if d.orig_page >= 0})
    scan_pages_needed = sorted({d.scan_page for d in diffs if d.scan_page >= 0})

    orig_imgs = _render_pages(cmp.orig_file.path, orig_pages_needed, dpi)
    scan_imgs = _render_pages(cmp.scan_file.path, scan_pages_needed, dpi)

    # 按 (orig_page, scan_page) pair 分组
    pairs: dict[tuple, list[Diff]] = {}
    for d in diffs:
        key = (d.orig_page if d.orig_page >= 0 else None,
               d.scan_page if d.scan_page >= 0 else None)
        pairs.setdefault(key, []).append(d)

    sections = []
    for (op, sp), pdiffs in sorted(pairs.items(), key=lambda x: (
        x[0][1] if x[0][1] is not None else 9999,
        x[0][0] if x[0][0] is not None else 9999
    )):
        sections.append(_render_section(op, sp, pdiffs, orig_imgs, scan_imgs))

    # 摘要
    s = cmp.summary_json or {}
    summary_html = f"""
<div class="summary">
  <div class="card real"><div class="num">{s.get('real', 0)}</div><div class="lab">真实差异</div></div>
  <div class="card critical"><div class="num">{s.get('critical', 0)}</div><div class="lab">关键字段</div></div>
  <div class="card"><div class="num">{s.get('replace', 0)}</div><div class="lab">修改</div></div>
  <div class="card"><div class="num">{s.get('delete', 0)}</div><div class="lab">删除</div></div>
  <div class="card"><div class="num">{s.get('insert', 0) + s.get('handwritten', 0)}</div><div class="lab">新增</div></div>
  <div class="card"><div class="num">{s.get('stamp_covered', 0)}</div><div class="lab">章遮挡</div></div>
</div>
"""

    reviewed_n = sum(1 for d in diffs if d.review_action)
    confirmed_n = sum(1 for d in diffs if d.review_action == ReviewAction.confirmed)
    ignored_n = sum(1 for d in diffs if d.review_action == ReviewAction.ignored)
    review_html = f"""
<div class="review-summary">
  <span>审核进度：<b>{reviewed_n} / {len(diffs)}</b></span>
  <span class="ok">✓ 确认 {confirmed_n}</span>
  <span class="ig">✗ 忽略 {ignored_n}</span>
  <span class="un">未审核 {len(diffs) - reviewed_n}</span>
</div>
"""

    title = html.escape(cmp.title or f"对比 #{cmp.id}")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title} - 审核报告</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "PingFang SC", "Helvetica Neue", sans-serif; background: #f5f6f8; color: #1f2937; }}
.top {{ background: #fff; padding: 16px 24px; border-bottom: 1px solid #e5e7eb; border-top: 3px solid #2563eb; }}
.top h1 {{ margin: 0 0 4px; font-size: 18px; }}
.top .meta {{ font-size: 12px; color: #6b7280; }}
.summary {{ display: flex; gap: 12px; padding: 12px 24px; background: #fff; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }}
.card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 16px; min-width: 90px; }}
.card.critical {{ background: #fef2f2; border-color: #fecaca; }}
.card.real {{ background: #fff7ed; border-color: #fdba74; }}
.num {{ font-size: 22px; font-weight: 600; }}
.lab {{ font-size: 12px; color: #6b7280; }}
.review-summary {{ padding: 8px 24px; background: #fafbfc; border-bottom: 1px solid #e5e7eb; font-size: 13px; display: flex; gap: 16px; }}
.review-summary .ok {{ color: #dc2626; font-weight: 500; }}
.review-summary .ig {{ color: #6b7280; }}
.review-summary .un {{ color: #d97706; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 14px; padding: 8px 24px; background: #fafbfc; border-bottom: 1px solid #e5e7eb; font-size: 12px; color: #444; }}
.lg-sw {{ display: inline-block; width: 14px; height: 12px; border: 1px solid #888; border-radius: 2px; vertical-align: middle; margin-right: 4px; }}
section.pair {{ background: #fff; border-radius: 8px; padding: 12px; margin: 16px 24px; border: 1px solid #e5e7eb; }}
section.pair header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; font-size: 13px; font-weight: 600; }}
.dual {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.side {{ position: relative; }}
.canvas-wrap {{ position: relative; width: 100%; border: 1px solid #d1d5db; background: #fff; }}
.canvas-wrap img {{ width: 100%; display: block; }}
.hl {{ position: absolute; border: 2px solid rgba(0,0,0,0.4); border-radius: 2px; }}
.diff-list {{ margin-top: 12px; }}
.diff-row {{ padding: 8px 12px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 8px; font-size: 13px; }}
.diff-row.confirmed {{ border-left: 4px solid #dc2626; background: #fef2f2; }}
.diff-row.ignored {{ border-left: 4px solid #9ca3af; background: #f9fafb; opacity: 0.7; }}
.badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px; }}
.badge-replace {{ background: #fef3c7; color: #92400e; }}
.badge-delete {{ background: #fee2e2; color: #991b1b; }}
.badge-insert, .badge-handwritten {{ background: #dcfce7; color: #14532d; }}
.badge-stamp_covered {{ background: #e5e7eb; color: #555; }}
.badge-critical {{ background: #dc2626; color: #fff; }}
.diff-text {{ font-family: ui-monospace, Menlo, monospace; font-size: 12px; margin-top: 4px; }}
.diff-text .orig {{ color: #991b1b; }}
.diff-text .scan {{ color: #14532d; }}
.diff-note {{ color: #6b7280; font-style: italic; margin-top: 4px; }}
.empty {{ padding: 40px; text-align: center; color: #9ca3af; border: 1px dashed #d1d5db; border-radius: 4px; }}
@media print {{ body {{ background: #fff; }} section.pair {{ page-break-inside: avoid; box-shadow: none; }} }}
</style>
</head>
<body>
<div class="top">
  <h1>📋 PDF 差异对比审核报告</h1>
  <div class="meta">
    {title} · #{cmp.id} · 生成于 {generated_at}
    {' · 原件: ' + html.escape(cmp.orig_file.original_name) if cmp.orig_file else ''}
    {' · 扫描件: ' + html.escape(cmp.scan_file.original_name) if cmp.scan_file else ''}
  </div>
</div>
{summary_html}
{review_html}
<div class="legend">
  <span><span class="lg-sw" style="background:rgba(34,197,94,0.5);"></span>新增</span>
  <span><span class="lg-sw" style="background:rgba(239,68,68,0.45);"></span>删除</span>
  <span><span class="lg-sw" style="background:rgba(250,204,21,0.55);"></span>修改</span>
  <span><span class="lg-sw" style="background:rgba(180,180,180,0.45);"></span>章遮挡</span>
  <span style="color:#dc2626;">★ 关键字段</span>
</div>
{''.join(sections) or '<div class="empty">无需关注的差异</div>'}
</body>
</html>
""".encode("utf-8")


def _render_pages(pdf_path: str, page_indices: list[int], dpi: int) -> dict[int, tuple[str, int, int, float, float]]:
    """渲染指定页到 PNG base64。返回 {page_idx: (b64, img_w, img_h, pt_w, pt_h)}"""
    out: dict = {}
    if not page_indices:
        return out
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0
    try:
        for i in page_indices:
            if i < 0 or i >= len(doc):
                continue
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            out[i] = (b64, pix.width, pix.height, page.rect.width, page.rect.height)
    finally:
        doc.close()
    return out


def _render_section(op: int | None, sp: int | None, diffs: list[Diff],
                    orig_imgs: dict, scan_imgs: dict) -> str:
    """渲染一对 (原件页, 扫描件页) 的并排区块。"""
    label = f"原件 P{(op + 1) if op is not None else '—'} ↔ 扫描件 P{(sp + 1) if sp is not None else '—'}"
    diff_count = len(diffs)

    orig_html = _render_side(op, orig_imgs, "orig", diffs)
    scan_html = _render_side(sp, scan_imgs, "scan", diffs)

    diff_rows = []
    for d in diffs:
        klass = ""
        if d.review_action == ReviewAction.confirmed:
            klass = "confirmed"
        elif d.review_action == ReviewAction.ignored:
            klass = "ignored"
        sev = '<span class="badge badge-critical">★ 关键</span>' if d.severity == DiffSeverity.critical else ""
        review = ""
        if d.review_action == ReviewAction.confirmed:
            review = '<span style="color:#dc2626;font-weight:500;">✓ 确认</span>'
        elif d.review_action == ReviewAction.ignored:
            review = '<span style="color:#6b7280;">✗ 忽略</span>'
        note = f'<div class="diff-note">💬 {html.escape(d.review_note)}</div>' if d.review_note else ""

        diff_rows.append(f"""
<div class="diff-row {klass}">
  <span class="badge badge-{d.category.value}">{CATEGORY_LABEL.get(d.category.value, d.category.value)}</span>
  {sev}
  <span style="color:#6b7280;">#{d.seq_no}</span>
  {review}
  <div class="diff-text">
    {'<div class="orig">原：' + html.escape(d.orig_text) + '</div>' if d.orig_text else ''}
    {'<div class="scan">扫：' + html.escape(d.scan_text) + '</div>' if d.scan_text else ''}
  </div>
  {note}
</div>""")

    return f"""
<section class="pair">
  <header>
    📄 {label}
    <span style="margin-left:auto;color:#6b7280;font-weight:400;">{diff_count} 处差异</span>
  </header>
  <div class="dual">
    <div class="side">{orig_html}</div>
    <div class="side">{scan_html}</div>
  </div>
  <div class="diff-list">{''.join(diff_rows)}</div>
</section>
"""


def _render_side(page_idx: int | None, imgs: dict, side: str, diffs: list[Diff]) -> str:
    if page_idx is None or page_idx not in imgs:
        return '<div class="empty">该页无对应内容</div>'
    b64, iw, ih, pw, ph = imgs[page_idx]
    sx = iw / pw
    sy = ih / ph
    overlays = []
    for d in diffs:
        bbox = d.orig_bbox if side == "orig" else d.scan_bbox
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        left = (x0 * sx) / iw * 100
        top = (y0 * sy) / ih * 100
        width = ((x1 - x0) * sx) / iw * 100
        height = ((y1 - y0) * sy) / ih * 100
        bg = CATEGORY_COLOR.get(d.category.value, "rgba(255,165,0,0.4)")
        overlays.append(
            f'<div class="hl" style="left:{left:.3f}%;top:{top:.3f}%;'
            f'width:{max(width, 0.5):.3f}%;height:{max(height, 0.5):.3f}%;background:{bg};"></div>'
        )
    return f'<div class="canvas-wrap"><img src="data:image/png;base64,{b64}"/>{"".join(overlays)}</div>'

"""PDF 审核报告导出（reportlab）。

输出内容：
- 封面：标题 + 任务信息 + 摘要统计
- 关键差异清单（critical 优先）
- 全部差异清单
- 审核结论汇总

字体：内置 CJK 字体 STSong-Light（reportlab 自带），无需额外字体文件。
"""
from __future__ import annotations
import io
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from app.db.models import Comparison, Diff, DiffCategory, DiffSeverity, ReviewAction, User


# 注册一次内置 CJK 字体
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
CN_FONT = "STSong-Light"


CATEGORY_LABEL = {
    "replace": "修改", "delete": "删除", "insert": "新增",
    "handwritten": "手写填空", "stamp_covered": "章遮挡", "moved": "位置移动",
}

CATEGORY_BG = {
    "replace": colors.HexColor("#FEF3C7"),
    "delete": colors.HexColor("#FEE2E2"),
    "insert": colors.HexColor("#DCFCE7"),
    "handwritten": colors.HexColor("#DCFCE7"),
    "stamp_covered": colors.HexColor("#E5E7EB"),
    "moved": colors.HexColor("#DBEAFE"),
}


def export_pdf(db: Session, comparison_id: int) -> bytes:
    cmp = db.get(Comparison, comparison_id)
    if not cmp:
        raise ValueError("Comparison 不存在")

    diffs_all = db.scalars(
        select(Diff).where(Diff.comparison_id == comparison_id).order_by(Diff.seq_no.asc())
    ).all()
    # 排除噪声
    real_diffs = [
        d for d in diffs_all
        if d.category != DiffCategory.moved
        and d.severity != DiffSeverity.info
        and not d.is_footer
    ]
    critical_diffs = [d for d in real_diffs if d.severity == DiffSeverity.critical]

    # 收集审核人
    reviewer_ids = {d.reviewed_by for d in real_diffs if d.reviewed_by}
    reviewer_map = {}
    if reviewer_ids:
        users = db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()
        reviewer_map = {u.id: u.display_name or u.username for u in users}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"PDF 对比报告 #{cmp.id}",
    )

    styles = _make_styles()
    story: list = []

    # ── 封面 ──
    story.append(Paragraph("PDF 差异对比审核报告", styles["title"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"任务标题：{cmp.title or '—'}", styles["body"]))
    story.append(Paragraph(f"任务编号：#{cmp.id}", styles["body"]))
    story.append(Paragraph(f"原件文件：{cmp.orig_file.original_name if cmp.orig_file else '—'}", styles["body"]))
    story.append(Paragraph(f"扫描件文件：{cmp.scan_file.original_name if cmp.scan_file else '—'}", styles["body"]))
    story.append(Paragraph(f"创建时间：{_fmt(cmp.created_at)}", styles["body"]))
    story.append(Paragraph(f"完成时间：{_fmt(cmp.completed_at)}", styles["body"]))
    story.append(Paragraph(
        f"审核完成：{_fmt(cmp.review_completed_at)} "
        f"· 审核人：{reviewer_map.get(cmp.review_completed_by, '—') if cmp.review_completed_by else '—'}",
        styles["body"]
    ))
    story.append(Paragraph(f"报告生成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["meta"]))
    story.append(Spacer(1, 8 * mm))

    # ── 摘要表 ──
    s = cmp.summary_json or {}
    story.append(Paragraph("差异统计", styles["h2"]))
    summary_table_data = [
        ["真实差异", str(s.get("real", 0))],
        ["★ 关键字段", str(s.get("critical", 0))],
        ["修改", str(s.get("replace", 0))],
        ["删除", str(s.get("delete", 0))],
        ["新增（含手写填空）", str(s.get("insert", 0) + s.get("handwritten", 0))],
        ["章遮挡", str(s.get("stamp_covered", 0))],
        ["位置移动（噪声）", str(s.get("moved", 0))],
    ]
    sum_table = Table(summary_table_data, colWidths=[60 * mm, 30 * mm])
    sum_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), CN_FONT, 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F9FAFB")),
        ("BACKGROUND", (0, 1), (1, 1), colors.HexColor("#FEF2F2")),  # 关键字段那行
        ("TEXTCOLOR", (0, 1), (1, 1), colors.HexColor("#DC2626")),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 5 * mm))

    # ── 审核进度 ──
    reviewed_n = sum(1 for d in real_diffs if d.review_action)
    confirmed_n = sum(1 for d in real_diffs if d.review_action == ReviewAction.confirmed)
    ignored_n = sum(1 for d in real_diffs if d.review_action == ReviewAction.ignored)
    story.append(Paragraph(
        f"审核进度：{reviewed_n} / {len(real_diffs)} "
        f"（确认 <font color='#DC2626'><b>{confirmed_n}</b></font> · "
        f"忽略 {ignored_n} · 未审核 {len(real_diffs) - reviewed_n}）",
        styles["body"]
    ))

    # ── 关键差异 ──
    story.append(PageBreak())
    story.append(Paragraph("★ 关键差异（critical）", styles["h2"]))
    if critical_diffs:
        story.append(_diff_table(critical_diffs, reviewer_map))
    else:
        story.append(Paragraph("无关键字段差异。", styles["body"]))
    story.append(Spacer(1, 4 * mm))

    # ── 全部真实差异 ──
    story.append(PageBreak())
    story.append(Paragraph("全部真实差异", styles["h2"]))
    if real_diffs:
        story.append(_diff_table(real_diffs, reviewer_map))
    else:
        story.append(Paragraph("无差异。", styles["body"]))

    doc.build(story)
    return buf.getvalue()


def _make_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName=CN_FONT, fontSize=20, leading=26,
            textColor=colors.HexColor("#1F2937"),
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=CN_FONT, fontSize=14, leading=18,
            spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#1F2937"),
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName=CN_FONT, fontSize=10, leading=14,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["BodyText"], fontName=CN_FONT, fontSize=9, leading=12,
            textColor=colors.HexColor("#6B7280"),
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["BodyText"], fontName=CN_FONT, fontSize=8, leading=11,
        ),
        "cell_red": ParagraphStyle(
            "cell_red", parent=base["BodyText"], fontName=CN_FONT, fontSize=8, leading=11,
            textColor=colors.HexColor("#991B1B"),
        ),
        "cell_green": ParagraphStyle(
            "cell_green", parent=base["BodyText"], fontName=CN_FONT, fontSize=8, leading=11,
            textColor=colors.HexColor("#14532D"),
        ),
    }


def _diff_table(diffs: list[Diff], reviewer_map: dict) -> Table:
    styles = _make_styles()
    header = ["#", "类别", "页", "原件文本", "扫描件文本", "审核", "批注"]
    rows = [header]
    for d in diffs:
        page = (d.scan_page if d.scan_page >= 0 else d.orig_page) + 1
        cat_text = ("★ " if d.severity == DiffSeverity.critical else "") + \
                   CATEGORY_LABEL.get(d.category.value, d.category.value)
        review_text = "—"
        if d.review_action == ReviewAction.confirmed:
            review_text = "✓ 确认"
        elif d.review_action == ReviewAction.ignored:
            review_text = "✗ 忽略"
        rows.append([
            str(d.seq_no),
            Paragraph(cat_text, styles["cell"]),
            str(page),
            Paragraph((d.orig_text or "")[:120], styles["cell_red"]),
            Paragraph((d.scan_text or "")[:120], styles["cell_green"]),
            Paragraph(review_text, styles["cell"]),
            Paragraph((d.review_note or "")[:60], styles["cell"]),
        ])

    col_widths = [9 * mm, 18 * mm, 9 * mm, 45 * mm, 45 * mm, 14 * mm, 32 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, -1), CN_FONT, 8),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]
    # 按类别给"类别"列填色
    for i, d in enumerate(diffs, start=1):
        bg = CATEGORY_BG.get(d.category.value)
        if bg:
            style.append(("BACKGROUND", (1, i), (1, i), bg))
        if d.review_action == ReviewAction.confirmed:
            style.append(("BACKGROUND", (5, i), (5, i), colors.HexColor("#FEE2E2")))
            style.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#991B1B")))
        elif d.review_action == ReviewAction.ignored:
            style.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#6B7280")))
    table.setStyle(TableStyle(style))
    return table


def _fmt(dt) -> str:
    if not dt:
        return "—"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)

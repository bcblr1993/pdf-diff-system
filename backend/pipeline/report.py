"""生成 HTML 并排高亮报告。"""
from __future__ import annotations
import base64
import io
import json
import html
import fitz
from PIL import Image


CATEGORY_COLOR = {
    # 黄色 = 修改
    "replace": "rgba(250, 204, 21, 0.55)",
    # 红色 = 删除（原件有扫描件没了）
    "delete": "rgba(239, 68, 68, 0.45)",
    # 绿色 = 新增（扫描件多出来）
    "insert": "rgba(34, 197, 94, 0.50)",
    "handwritten": "rgba(34, 197, 94, 0.50)",
    # 灰色 = 章遮挡
    "stamp_covered": "rgba(180, 180, 180, 0.45)",
    # 蓝色 = 位置移动
    "moved": "rgba(135, 180, 255, 0.35)",
}

CATEGORY_LABEL = {
    "replace": "修改",
    "delete": "删除",
    "insert": "新增",
    "handwritten": "手写填空",
    "stamp_covered": "章遮挡(不可信)",
    "moved": "位置移动",
}

# 噪声类别：默认折叠，不算"真差异"
NOISE_CATEGORIES = {"moved"}


def render_page_to_b64(pdf_path: str, page_no: int, dpi: int = 110) -> tuple[str, int, int, float, float]:
    """渲染 PDF 单页为 base64 PNG，返回 (data, img_w, img_h, page_w_pt, page_h_pt)。"""
    doc = fitz.open(pdf_path)
    page = doc[page_no]
    pw, ph = page.rect.width, page.rect.height
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    doc.close()
    return b64, pix.width, pix.height, pw, ph


def build_report(
    orig_pdf: str,
    scan_pdf: str,
    page_pairs: list[tuple[int | None, int | None]],
    diffs_per_pair: list[list],
    output_path: str,
    dpi: int = 110,
):
    """生成 HTML 报告：左右并排显示每页，叠加高亮框，附带差异列表。"""
    sections_html = []
    sidebar_rows = []
    summary = {
        "total": 0, "real": 0, "critical": 0, "replace": 0, "handwritten": 0,
        "stamp_covered": 0, "delete": 0, "insert": 0, "moved": 0, "footer": 0,
    }

    for idx, ((op, sp), diffs) in enumerate(zip(page_pairs, diffs_per_pair)):
        orig_html = _render_side(orig_pdf, op, "orig", diffs, dpi)
        scan_html = _render_side(scan_pdf, sp, "scan", diffs, dpi)
        diff_count = len(diffs)
        section = f"""
<section class="page-pair" id="pair-{idx}">
  <header>
    <span class="page-label">原件 P{op + 1 if op is not None else '—'}</span>
    <span class="vs">VS</span>
    <span class="page-label">扫描件 P{sp + 1 if sp is not None else '—'}</span>
    <span class="diff-count">{diff_count} 处差异</span>
  </header>
  <div class="dual">
    <div class="side">{orig_html}</div>
    <div class="side">{scan_html}</div>
  </div>
</section>
"""
        sections_html.append(section)

        for d in diffs:
            summary["total"] += 1
            summary[d.category] = summary.get(d.category, 0) + 1
            is_footer = getattr(d, "is_footer", False)
            is_info = d.severity == "info"
            is_noise = d.category in NOISE_CATEGORIES or is_footer or is_info
            if is_footer:
                summary["footer"] += 1
            if not is_noise:
                summary["real"] += 1
            if d.severity == "critical":
                summary["critical"] += 1
            extra_cls = " noise" if is_noise else ""
            row = f"""
<tr class="diff-row sev-{d.severity}{extra_cls}" data-pair="pair-{idx}" data-diffid="{d.id}" data-cat="{d.category}" data-footer="{1 if is_footer else 0}">
  <td><span class="badge badge-{d.category}">{CATEGORY_LABEL.get(d.category, d.category)}</span>{' <span class="tag">页脚</span>' if is_footer else ''}</td>
  <td>P{(d.orig_page if d.orig_page >= 0 else d.scan_page) + 1}</td>
  <td class="text-cell">{_escape(_trim(d.orig_text)) or '<i>—</i>'}</td>
  <td class="text-cell">{_escape(_trim(d.scan_text)) or '<i>—</i>'}</td>
  <td class="ctx">{_escape(_trim(d.context, 60))}</td>
</tr>"""
            sidebar_rows.append(row)

    summary_html = f"""
<div class="summary">
  <div class="card real"><div class="num">{summary['real']}</div><div class="lab">真实差异</div></div>
  <div class="card critical"><div class="num">{summary['critical']}</div><div class="lab">关键字段</div></div>
  <div class="card"><div class="num">{summary['replace']}</div><div class="lab">正文差异</div></div>
  <div class="card"><div class="num">{summary['handwritten']}</div><div class="lab">手写填空</div></div>
  <div class="card"><div class="num">{summary['stamp_covered']}</div><div class="lab">章遮挡</div></div>
  <div class="card noise"><div class="num">{summary['moved']}</div><div class="lab">位置移动</div></div>
  <div class="card noise"><div class="num">{summary['footer']}</div><div class="lab">页眉页脚</div></div>
  <div class="card"><div class="num">{summary['total']}</div><div class="lab">总计(含噪声)</div></div>
</div>
<div class="legend">
  <span class="lg-item"><span class="lg-sw" style="background:rgba(34,197,94,0.50);"></span> 绿色 = 新增（扫描件多出来的内容）</span>
  <span class="lg-item"><span class="lg-sw" style="background:rgba(239,68,68,0.45);"></span> 红色 = 删除（原件有扫描件没了）</span>
  <span class="lg-item"><span class="lg-sw" style="background:rgba(250,204,21,0.55);"></span> 黄色 = 修改（内容被改动）</span>
  <span class="lg-item"><span class="lg-sw" style="background:rgba(180,180,180,0.45);"></span> 灰色 = 红章遮挡区（OCR 不可信）</span>
  <span class="lg-item"><span class="lg-sw" style="background:rgba(135,180,255,0.35);"></span> 蓝色 = 位置移动（同内容换位，默认隐藏）</span>
  <span class="lg-item critical-tag">★ 红星 = 关键字段（金额/合同号/账号等）</span>
</div>
<div class="filter-bar">
  <label><input type="checkbox" id="show-noise"> 显示位移/页脚等噪声</label>
</div>
"""

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>PDF 差异对比报告</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "PingFang SC", "Helvetica Neue", sans-serif; background: #f5f6f8; color: #222; }}
header.top {{ position: sticky; top: 0; background: #fff; border-bottom: 1px solid #e5e7eb; padding: 12px 24px; z-index: 100; }}
header.top h1 {{ margin: 0; font-size: 16px; }}
.summary {{ display: flex; gap: 12px; padding: 12px 24px; background: #fff; border-bottom: 1px solid #e5e7eb; }}
.summary .card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 16px; min-width: 90px; }}
.summary .card.critical {{ background: #fef2f2; border-color: #fecaca; }}
.summary .card.real {{ background: #fff7ed; border-color: #fdba74; }}
.summary .card.noise {{ opacity: 0.6; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 14px; padding: 8px 24px; background: #fafbfc; border-bottom: 1px solid #e5e7eb; font-size: 12px; color: #444; }}
.lg-item {{ display: inline-flex; align-items: center; gap: 4px; }}
.lg-sw {{ display: inline-block; width: 14px; height: 12px; border: 1px solid #888; border-radius: 2px; }}
.critical-tag {{ color: #dc2626; font-weight: 500; }}
.filter-bar {{ padding: 8px 24px; background: #fff; border-bottom: 1px solid #e5e7eb; font-size: 13px; color: #555; }}
.diff-row.noise {{ display: none; }}
body.show-noise .diff-row.noise {{ display: table-row; opacity: 0.6; }}
.hl.noise-hl {{ display: none; }}
body.show-noise .hl.noise-hl {{ display: block; }}
.tag {{ display: inline-block; padding: 1px 5px; margin-left: 4px; background: #eef2ff; color: #3730a3; border-radius: 3px; font-size: 10px; }}
.summary .num {{ font-size: 22px; font-weight: 600; }}
.summary .lab {{ font-size: 12px; color: #666; }}
.layout {{ display: grid; grid-template-columns: 1fr 380px; }}
main {{ padding: 16px 24px; }}
aside {{ position: sticky; top: 100px; height: calc(100vh - 100px); overflow-y: auto; background: #fff; border-left: 1px solid #e5e7eb; padding: 12px; }}
aside table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
aside th, aside td {{ text-align: left; padding: 6px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
aside th {{ background: #f9fafb; position: sticky; top: 0; }}
.diff-row {{ cursor: pointer; }}
.diff-row:hover {{ background: #f3f4f6; }}
.sev-critical td:first-child::before {{ content: "★ "; color: #dc2626; }}
.badge {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
.badge-replace {{ background: #fef3c7; color: #92400e; }}
.badge-delete {{ background: #fee2e2; color: #991b1b; }}
.badge-insert, .badge-handwritten {{ background: #dcfce7; color: #14532d; }}
.badge-stamp_covered {{ background: #e5e7eb; color: #555; }}
.badge-moved {{ background: #dbeafe; color: #1e3a8a; }}
section.page-pair {{ background: #fff; border-radius: 8px; padding: 12px; margin-bottom: 24px; border: 1px solid #e5e7eb; }}
section.page-pair header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; font-size: 13px; }}
.page-label {{ font-weight: 600; }}
.vs {{ color: #888; font-size: 11px; }}
.diff-count {{ margin-left: auto; color: #666; font-size: 12px; }}
.dual {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.side {{ position: relative; }}
.page-canvas {{ position: relative; width: 100%; border: 1px solid #d1d5db; background: #fff; }}
.page-canvas img {{ width: 100%; display: block; }}
.hl {{ position: absolute; border: 2px solid; border-radius: 2px; pointer-events: auto; }}
.hl:hover {{ outline: 2px solid #fbbf24; }}
.text-cell {{ font-family: ui-monospace, Menlo, monospace; max-width: 110px; word-break: break-all; }}
.ctx {{ color: #666; font-size: 11px; max-width: 130px; }}
.empty {{ padding: 60px 0; text-align: center; color: #999; border: 1px dashed #d1d5db; border-radius: 4px; }}
</style>
</head>
<body>
<header class="top"><h1>PDF 差异对比报告 — {html.escape(_filename(orig_pdf))} vs {html.escape(_filename(scan_pdf))}</h1></header>
{summary_html}
<div class="layout">
  <main>
    {''.join(sections_html)}
  </main>
  <aside>
    <table>
      <thead><tr><th>类型</th><th>页</th><th>原件</th><th>扫描件</th><th>上下文</th></tr></thead>
      <tbody>{''.join(sidebar_rows)}</tbody>
    </table>
  </aside>
</div>
<script>
const noiseCk = document.getElementById('show-noise');
noiseCk && noiseCk.addEventListener('change', e => {{
  document.body.classList.toggle('show-noise', e.target.checked);
}});
document.querySelectorAll('.diff-row').forEach(r => {{
  r.addEventListener('click', () => {{
    const el = document.getElementById(r.dataset.pair);
    if (el) el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
    document.querySelectorAll('.hl-active').forEach(h => h.classList.remove('hl-active'));
    const tgt = document.querySelector('[data-diffid="' + r.dataset.diffid + '"].hl');
    if (tgt) {{ tgt.classList.add('hl-active'); tgt.style.outline = '3px solid #fbbf24'; setTimeout(() => tgt.style.outline = '', 2000); }}
  }});
}});
</script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return summary


def _render_side(pdf_path: str, page_no: int | None, side: str, diffs: list, dpi: int) -> str:
    if page_no is None:
        return '<div class="empty">该页无对应内容</div>'
    b64, iw, ih, pw, ph = render_page_to_b64(pdf_path, page_no, dpi=dpi)
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
        color = CATEGORY_COLOR.get(d.category, "rgba(255,165,0,0.4)")
        border_color = "rgba(0,0,0,0.5)"
        title = f"[{CATEGORY_LABEL.get(d.category, d.category)}] {_trim(d.orig_text or '—', 30)} → {_trim(d.scan_text or '—', 30)}"
        is_footer = getattr(d, "is_footer", False)
        extra = " noise-hl" if (d.category in NOISE_CATEGORIES or is_footer) else ""
        overlays.append(
            f'<div class="hl{extra}" data-diffid="{d.id}" title="{html.escape(title)}" '
            f'style="left:{left:.3f}%;top:{top:.3f}%;width:{width:.3f}%;height:{height:.3f}%;'
            f'background:{color};border-color:{border_color};"></div>'
        )
    return f'<div class="page-canvas"><img src="data:image/png;base64,{b64}"/>{"".join(overlays)}</div>'


def _trim(s: str, n: int = 24) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _escape(s: str) -> str:
    return html.escape(s or "")


def _filename(p: str) -> str:
    import os
    return os.path.basename(p)

"""字符流：把页内 (text, bbox) 展开为字符级序列，并维护反查表。

v3 升级：支持构建跨页"文档级"字符流，diff 不再受页号错位影响。
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from .normalize import LOOKALIKE


@dataclass
class Char:
    ch: str
    bbox: tuple[float, float, float, float]
    page: int
    line_bbox: tuple[float, float, float, float]
    line_id: int                  # 行 id（同页内唯一，跨页用 (page, line_id) 唯一）
    line_text: str
    is_footer: bool = False


@dataclass
class PageStream:
    page: int
    chars: list[Char] = field(default_factory=list)
    norm_text: str = ""
    norm_to_orig: list[int] = field(default_factory=list)


@dataclass
class DocStream:
    """文档级字符流（所有页拼接）。"""
    chars: list[Char] = field(default_factory=list)
    norm_text: str = ""
    norm_to_orig: list[int] = field(default_factory=list)  # norm 第 i 个字符 → chars 索引
    page_starts: list[int] = field(default_factory=list)   # 每页第一个 char 在 chars 中的索引


FOOTER_PATTERNS = [
    re.compile(r"^共\s*\d+\s*页\s*第\s*\d+\s*页$"),
    re.compile(r"^-?\s*\d+\s*-?$"),
    re.compile(r"^第\s*\d+\s*页$"),
]


def _is_footer_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    return any(p.match(t) for p in FOOTER_PATTERNS)


def _split_char_bboxes(text: str, bbox: tuple[float, float, float, float]) -> list[tuple]:
    n = len(text)
    if n == 0:
        return []
    x0, y0, x1, y1 = bbox
    w = (x1 - x0) / n
    return [(x0 + i * w, y0, x0 + (i + 1) * w, y1) for i in range(n)]


# OCR 噪声字符：扫描件 OCR 经常把这些识别出来但原件无（或反之），
# 统一忽略可以消除大量误报。所有 PDF 通用。
_IGNORE_CHARS = set("_¯﹍﹎﹏~‾‗")  # 各种下划线/上划线，合同填空常见


def _normalize_char(ch: str) -> str:
    if not ch or ch.isspace() or ch in _IGNORE_CHARS:
        return ""
    nch = unicodedata.normalize("NFKC", ch)
    if not nch:
        return ""
    c = nch[0]
    if c.isspace() or c in _IGNORE_CHARS:
        return ""
    return LOOKALIKE.get(c, c)


def _sort_orig_lines(lines):
    """原件按视觉阅读顺序排序：先 y（行），再 x（列）。"""
    return sorted(lines, key=lambda L: (round(L.bbox[1] / 3), L.bbox[0]))


def build_stream_from_orig(page) -> PageStream:
    ps = PageStream(page=page.page)
    lines = _sort_orig_lines(page.lines)
    for li, line in enumerate(lines):
        is_footer = _is_footer_line(line.text)
        if line.spans:
            for sp in line.spans:
                ch_boxes = _split_char_bboxes(sp.text, sp.bbox)
                for ch, bb in zip(sp.text, ch_boxes):
                    ps.chars.append(Char(
                        ch=ch, bbox=bb, page=page.page,
                        line_bbox=line.bbox, line_id=li, line_text=line.text,
                        is_footer=is_footer,
                    ))
        else:
            ch_boxes = _split_char_bboxes(line.text, line.bbox)
            for ch, bb in zip(line.text, ch_boxes):
                ps.chars.append(Char(
                    ch=ch, bbox=bb, page=page.page,
                    line_bbox=line.bbox, line_id=li, line_text=line.text,
                    is_footer=is_footer,
                ))
    _build_norm_index_page(ps)
    return ps


def build_stream_from_scan(page) -> PageStream:
    ps = PageStream(page=page.page)
    for li, line in enumerate(page.lines):
        is_footer = _is_footer_line(line.text)
        ch_boxes = _split_char_bboxes(line.text, line.bbox)
        for ch, bb in zip(line.text, ch_boxes):
            ps.chars.append(Char(
                ch=ch, bbox=bb, page=page.page,
                line_bbox=line.bbox, line_id=li, line_text=line.text,
                is_footer=is_footer,
            ))
    _build_norm_index_page(ps)
    return ps


def _build_norm_index_page(ps: PageStream):
    chars: list[str] = []
    idx_map: list[int] = []
    for i, c in enumerate(ps.chars):
        nc = _normalize_char(c.ch)
        if not nc:
            continue
        chars.append(nc)
        idx_map.append(i)
    ps.norm_text = "".join(chars)
    ps.norm_to_orig = idx_map


def build_doc_stream(page_streams: list[PageStream], *, skip_footer: bool = True) -> DocStream:
    """把多个 PageStream 合并成文档级字符流。
    skip_footer=True 时把页眉页脚字符从规范化串里排除（仍保留在 chars 里，避免索引错位）。
    """
    ds = DocStream()
    chars: list[str] = []
    idx_map: list[int] = []
    for ps in page_streams:
        ds.page_starts.append(len(ds.chars))
        for c in ps.chars:
            ds.chars.append(c)
            if skip_footer and c.is_footer:
                continue
            nc = _normalize_char(c.ch)
            if not nc:
                continue
            chars.append(nc)
            idx_map.append(len(ds.chars) - 1)
    ds.norm_text = "".join(chars)
    ds.norm_to_orig = idx_map
    return ds

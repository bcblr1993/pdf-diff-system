"""Word (.docx) 文本抽取。

将 docx 解析为段落字符流，直接喂给 diff_documents：
- 段落 / 表格单元格按文档顺序展开
- 每个段落对应一个 Line（带"段落索引"作为虚拟坐标）
- 复用 stream.PageStream 数据结构，但所有内容放在 page=0（Word 无页概念）
- 字符 bbox 用"段落 idx + char offset"的虚拟坐标：(0, para_idx*20, 0, para_idx*20+18)
  ——前端基于 line_id + char offset 反向渲染高亮，不依赖物理坐标

依赖：python-docx
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator
import zipfile

try:
    from docx import Document  # python-docx
except ImportError:
    Document = None  # type: ignore


@dataclass
class WordLine:
    """一个段落或表格单元格的文本。"""
    text: str
    para_idx: int                       # 段落顺序号（全局唯一）
    line_text: str = ""                 # 同 text（与 PdfLine 对齐）
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    spans: list = field(default_factory=list)

    def __post_init__(self):
        if not self.line_text:
            self.line_text = self.text


@dataclass
class WordPage:
    """伪页：Word 文档整体当作一页。"""
    page: int = 0
    lines: list[WordLine] = field(default_factory=list)
    width: float = 600.0
    height: float = 0.0                 # 用段落数 * 20 推算
    image = None
    img_width: int = 0
    img_height: int = 0


def is_docx(path: str) -> bool:
    """轻量判断是不是 docx（zip 头 + 含 word/document.xml）。"""
    try:
        with zipfile.ZipFile(path) as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False


def extract_docx(path: str) -> list[WordPage]:
    """抽取 docx 全部文本（段落 + 表格单元格），返回单页结构。

    顺序规则：
    - 严格按文档主体 body 中的元素顺序：段落、表格逐个展开
    - 表格按行 → 单元格 → 单元格内段落 顺序
    - 空段落跳过（避免 OCR 那边没有的空白行参与 diff）
    """
    if Document is None:
        raise RuntimeError("python-docx 未安装")

    page = WordPage()
    para_idx = 0

    doc = Document(path)
    for para_idx_g, item in enumerate(_iter_block_items(doc)):
        # item 是段落 (Paragraph) 或表格 (Table)
        if hasattr(item, "text"):  # Paragraph
            text = (item.text or "").strip()
            if not text:
                continue
            page.lines.append(_make_line(text, para_idx))
            para_idx += 1
        else:  # Table
            for row in item.rows:
                for cell in row.cells:
                    cell_text = " ".join(
                        p.text.strip() for p in cell.paragraphs if p.text.strip()
                    )
                    if cell_text:
                        page.lines.append(_make_line(cell_text, para_idx))
                        para_idx += 1

    page.height = max(para_idx * 20.0, 100.0)
    return [page]


def _make_line(text: str, para_idx: int) -> WordLine:
    """根据段落索引生成"虚拟坐标"，bbox 用 (0, y, len*9, y+18)。"""
    y = para_idx * 20.0
    bbox = (0.0, y, max(len(text) * 9.0, 100.0), y + 18.0)
    line = WordLine(text=text, para_idx=para_idx, bbox=bbox)

    # 构造 span，让现有 build_stream_from_orig 能处理
    class _Span:
        def __init__(self, t, bb):
            self.text = t
            self.bbox = bb

    line.spans = [_Span(text, bbox)]
    return line


def _iter_block_items(parent):
    """按文档顺序产出段落和表格。

    python-docx 的 paragraphs / tables 是分开拿的，无法保留 body 顺序。
    本函数按底层 XML 元素的实际顺序遍历，保留段落和表格交错的顺序。
    """
    from docx.document import Document as _Doc
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import _Cell, Table
    from docx.text.paragraph import Paragraph

    if isinstance(parent, _Doc):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError(f"不支持的父级类型: {type(parent)}")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

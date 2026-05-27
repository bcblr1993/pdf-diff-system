"""原件 PDF 矢量文字抽取（带坐标）"""
from __future__ import annotations
import fitz
from dataclasses import dataclass, field


@dataclass
class TextSpan:
    text: str
    bbox: tuple[float, float, float, float]
    page: int


@dataclass
class TextLine:
    text: str
    bbox: tuple[float, float, float, float]
    page: int
    spans: list[TextSpan] = field(default_factory=list)


@dataclass
class PageText:
    page: int
    width: float
    height: float
    lines: list[TextLine]
    raw_text: str


def extract_pdf_text(pdf_path: str) -> list[PageText]:
    """用 PyMuPDF 直接抽取矢量文字。返回每页的行结构。"""
    doc = fitz.open(pdf_path)
    pages: list[PageText] = []
    for pno in range(len(doc)):
        page = doc[pno]
        rect = page.rect
        d = page.get_text("dict")
        lines: list[TextLine] = []
        raw_chunks: list[str] = []
        for block in d.get("blocks", []):
            if block.get("type") != 0:
                continue
            for ln in block.get("lines", []):
                spans = []
                texts = []
                for sp in ln.get("spans", []):
                    t = sp.get("text", "")
                    if not t:
                        continue
                    spans.append(TextSpan(text=t, bbox=tuple(sp["bbox"]), page=pno))
                    texts.append(t)
                if not spans:
                    continue
                line_text = "".join(texts)
                lines.append(
                    TextLine(
                        text=line_text,
                        bbox=tuple(ln["bbox"]),
                        page=pno,
                        spans=spans,
                    )
                )
                raw_chunks.append(line_text)
        pages.append(
            PageText(
                page=pno,
                width=rect.width,
                height=rect.height,
                lines=lines,
                raw_text="\n".join(raw_chunks),
            )
        )
    doc.close()
    return pages

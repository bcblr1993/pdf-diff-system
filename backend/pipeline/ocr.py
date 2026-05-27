"""扫描件 OCR：PDF → 图像 → RapidOCR → 带坐标的行结构"""
from __future__ import annotations
import fitz
import numpy as np
from dataclasses import dataclass, field
from rapidocr_onnxruntime import RapidOCR


@dataclass
class OcrLine:
    text: str
    bbox: tuple[float, float, float, float]  # PDF 坐标系（左上 origin），单位 pt
    page: int
    conf: float
    img_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)  # 原图像素坐标


@dataclass
class OcrPage:
    page: int
    width: float
    height: float
    img_width: int
    img_height: int
    lines: list[OcrLine]
    image: np.ndarray = field(default=None, repr=False)


# 单例
_OCR: RapidOCR | None = None


def get_ocr() -> RapidOCR:
    global _OCR
    if _OCR is None:
        _OCR = RapidOCR()
    return _OCR


def _quad_to_bbox(quad) -> tuple[int, int, int, int]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))


def ocr_pdf(pdf_path: str, dpi: int = 200) -> list[OcrPage]:
    """把扫描件 PDF 每页 render 成图像，做 OCR，返回带坐标的行。"""
    ocr = get_ocr()
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0
    pages: list[OcrPage] = []
    for pno in range(len(doc)):
        page = doc[pno]
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        # rapidocr 需要 BGR/RGB 三通道
        if img.shape[2] == 4:
            img = img[:, :, :3]
        result, _ = ocr(img)
        lines: list[OcrLine] = []
        if result:
            for item in result:
                quad, text, conf = item
                if not text or not text.strip():
                    continue
                ix0, iy0, ix1, iy1 = _quad_to_bbox(quad)
                # 图像坐标 → PDF pt 坐标
                px0 = ix0 / scale
                py0 = iy0 / scale
                px1 = ix1 / scale
                py1 = iy1 / scale
                lines.append(
                    OcrLine(
                        text=text,
                        bbox=(px0, py0, px1, py1),
                        page=pno,
                        conf=float(conf),
                        img_bbox=(ix0, iy0, ix1, iy1),
                    )
                )
        # 按 y 再 x 排序
        lines.sort(key=lambda L: (round(L.bbox[1] / 5), L.bbox[0]))
        pages.append(
            OcrPage(
                page=pno,
                width=page.rect.width,
                height=page.rect.height,
                img_width=pix.width,
                img_height=pix.height,
                lines=lines,
                image=img,
            )
        )
    doc.close()
    return pages

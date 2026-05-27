"""红章检测：HSV 提取红色，输出不可信区域的 bbox。"""
from __future__ import annotations
import cv2
import numpy as np


def detect_red_stamps(img_bgr_or_rgb: np.ndarray, min_area: int = 2000) -> list[tuple[int, int, int, int]]:
    """检测红色印章/手写笔迹区域。返回 [(x0,y0,x1,y1), ...] 像素坐标。

    输入可能是 RGB 或 BGR；红色判定对两者通用（红色 H 接近 0/180）。
    """
    if img_bgr_or_rgb.shape[2] == 3:
        # 假定输入是 RGB（PyMuPDF 输出），转 BGR 给 OpenCV
        bgr = cv2.cvtColor(img_bgr_or_rgb, cv2.COLOR_RGB2BGR)
    else:
        bgr = img_bgr_or_rgb
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # 红色在 HSV 里横跨两个区间
    m1 = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
    m2 = cv2.inRange(hsv, np.array([160, 50, 50]), np.array([180, 255, 255]))
    mask = cv2.bitwise_or(m1, m2)
    # 形态学闭运算填补
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    # 连通域
    num, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes: list[tuple[int, int, int, int]] = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < min_area:
            continue
        boxes.append((int(x), int(y), int(x + w), int(y + h)))
    return boxes


def bbox_in_any(bbox: tuple[float, float, float, float],
                regions: list[tuple[float, float, float, float]],
                overlap_ratio: float = 0.3) -> bool:
    """文本 bbox 与红章区域重叠超过阈值则判为受遮挡。"""
    x0, y0, x1, y1 = bbox
    area = max(1.0, (x1 - x0) * (y1 - y0))
    for rx0, ry0, rx1, ry1 in regions:
        ix0 = max(x0, rx0)
        iy0 = max(y0, ry0)
        ix1 = min(x1, rx1)
        iy1 = min(y1, ry1)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        inter = (ix1 - ix0) * (iy1 - iy0)
        if inter / area >= overlap_ratio:
            return True
    return False

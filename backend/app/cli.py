"""主入口：跑两份 PDF 的差异对比（v7：全文档 diff + move + 缓存）。"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from copy import deepcopy

from pipeline.extract import extract_pdf_text
from pipeline.ocr import ocr_pdf
from pipeline.stamp_mask import detect_red_stamps
from pipeline.stream import build_stream_from_orig, build_stream_from_scan, build_doc_stream
from pipeline.diff import diff_documents, DiffItem
from pipeline.report import build_report
from pipeline import cache as ocrcache


# CLI 旧版入口：保留命令行批处理能力，便于运维。容器中 cache 走容器卷。
CACHE_DIR = os.environ.get("CACHE_DIR") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "cache")
)


def _scale_stamp_to_pt(stamp_boxes_px, scale: float):
    return [(b[0] / scale, b[1] / scale, b[2] / scale, b[3] / scale) for b in stamp_boxes_px]


def _ocr_with_cache(pdf_path: str, dpi: int):
    """OCR + 章检测一并缓存。缓存 key 由文件 hash + dpi 决定。"""
    fh = ocrcache.file_hash(pdf_path)
    key = f"scan_{fh}_dpi{dpi}"
    cached = ocrcache.load(CACHE_DIR, key)
    if cached is not None:
        print(f"      ✓ 命中缓存 ({key})")
        scan_pages, stamp_regions = cached
        return scan_pages, stamp_regions, True

    print(f"      ✗ 未命中缓存，开始 OCR …")
    scan_pages = ocr_pdf(pdf_path, dpi=dpi)
    # 章检测 + 转 pt 坐标
    stamp_regions: dict[int, list[tuple[float, float, float, float]]] = {}
    for sp in scan_pages:
        boxes_px = detect_red_stamps(sp.image) if sp.image is not None else []
        scale = sp.img_width / sp.width
        stamp_regions[sp.page] = _scale_stamp_to_pt(boxes_px, scale)

    # 缓存前去掉 image（太大）
    scan_pages_compact = []
    for sp in scan_pages:
        sp2 = deepcopy(sp)
        sp2.image = None
        scan_pages_compact.append(sp2)
    ocrcache.save(CACHE_DIR, key, (scan_pages_compact, stamp_regions))
    return scan_pages, stamp_regions, False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--orig", required=True)
    parser.add_argument("--scan", required=True)
    parser.add_argument("--out", default="output/report.html")
    parser.add_argument("--json", default="output/diff.json")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--no-cache", action="store_true", help="强制重新 OCR")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    t0 = time.time()

    print(f"[1/4] 抽取原件文字 …")
    orig_pages = extract_pdf_text(args.orig)
    print(f"      原件 {len(orig_pages)} 页，总行数={sum(len(p.lines) for p in orig_pages)}")

    print(f"[2/4] OCR 扫描件 + 章检测 (dpi={args.dpi}) …")
    t1 = time.time()
    if args.no_cache:
        fh = ocrcache.file_hash(args.scan)
        cp = ocrcache.cache_path(CACHE_DIR, f"scan_{fh}_dpi{args.dpi}")
        if os.path.exists(cp):
            os.remove(cp)
    scan_pages, stamp_regions_per_page, hit = _ocr_with_cache(args.scan, args.dpi)
    print(f"      扫描件 {len(scan_pages)} 页，{'缓存命中' if hit else f'OCR 耗时 {time.time()-t1:.1f}s'}")
    print(f"      共检测到红章区域 {sum(len(x) for x in stamp_regions_per_page.values())} 处")

    print(f"[3/4] 构建文档级字符流 + 全文档 diff …")
    t2 = time.time()
    orig_streams = [build_stream_from_orig(p) for p in orig_pages]
    scan_streams = [build_stream_from_scan(p) for p in scan_pages]
    orig_doc = build_doc_stream(orig_streams, skip_footer=True)
    scan_doc = build_doc_stream(scan_streams, skip_footer=True)
    print(f"      原件字符流 {len(orig_doc.norm_text)} | 扫描件字符流 {len(scan_doc.norm_text)}")

    diffs = diff_documents(orig_doc, scan_doc, stamp_regions_per_page=stamp_regions_per_page)
    print(f"      diff 完成，{len(diffs)} 处差异，耗时 {time.time()-t2:.1f}s")

    print(f"[4/4] 渲染 HTML 报告 …")
    n_scan = len(scan_pages)
    n_orig = len(orig_pages)
    page_pairs = _infer_page_pairs(diffs, n_orig, n_scan)
    diffs_per_pair = _route_diffs(diffs, page_pairs)

    summary = build_report(args.orig, args.scan, page_pairs, diffs_per_pair, args.out)

    payload = {
        "summary": summary,
        "pages": [
            {
                "orig_page": op,
                "scan_page": sp,
                "diffs": [d.to_dict() for d in ds],
            }
            for (op, sp), ds in zip(page_pairs, diffs_per_pair)
        ],
    }
    os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n完成！总耗时 {time.time()-t0:.1f}s")
    print(f"  报告: {os.path.abspath(args.out)}")
    print(f"  JSON: {os.path.abspath(args.json)}")
    print(f"  摘要: {summary}")


def _infer_page_pairs(diffs, n_orig: int, n_scan: int):
    from collections import Counter
    s2o: dict[int, Counter] = {}
    for d in diffs:
        if d.scan_page < 0 or d.orig_page < 0:
            continue
        s2o.setdefault(d.scan_page, Counter())[d.orig_page] += 1
    pairs: list[tuple] = []
    used_orig: set[int] = set()
    last_op = -1
    for sp in range(n_scan):
        cands = s2o.get(sp, Counter())
        chosen = None
        for op, _ in cands.most_common():
            if op > last_op and op not in used_orig:
                chosen = op
                break
        if chosen is None:
            for op in range(last_op + 1, n_orig):
                if op not in used_orig:
                    chosen = op
                    break
        if chosen is not None:
            used_orig.add(chosen)
            last_op = chosen
        pairs.append((chosen, sp))
    for op in range(n_orig):
        if op not in used_orig:
            pairs.append((op, None))
    pairs.sort(key=lambda p: (p[1] if p[1] is not None else 9999, p[0] if p[0] is not None else 9999))
    return pairs


def _route_diffs(diffs, page_pairs):
    s2idx: dict[int, int] = {}
    o2idx: dict[int, int] = {}
    for i, (op, sp) in enumerate(page_pairs):
        if sp is not None:
            s2idx[sp] = i
        if op is not None:
            o2idx[op] = i
    buckets: list[list] = [[] for _ in page_pairs]
    for d in diffs:
        idx = None
        if d.scan_page >= 0 and d.scan_page in s2idx:
            idx = s2idx[d.scan_page]
        elif d.orig_page >= 0 and d.orig_page in o2idx:
            idx = o2idx[d.orig_page]
        else:
            idx = 0
        buckets[idx].append(d)
    return buckets


if __name__ == "__main__":
    sys.exit(main())

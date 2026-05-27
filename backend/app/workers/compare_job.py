"""RQ Job：跑一次完整的 pipeline。"""
from __future__ import annotations
import os
import time
from datetime import datetime, timezone
from collections import Counter
from sqlalchemy import select
from app.db.base import SessionLocal
from app.db.models import (
    Comparison, ComparisonStatus, Diff, DiffCategory, DiffSeverity
)
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.workers.queue import publish_progress


setup_logging()
log = get_logger("compare_job")


def _update_progress(cid: int, phase: str, pct: int, message: str = "") -> None:
    """更新 DB 进度字段 + 推送 Redis。"""
    publish_progress(cid, phase, pct, message)
    with SessionLocal() as db:
        cmp = db.get(Comparison, cid)
        if cmp:
            cmp.progress_phase = phase
            cmp.progress_pct = pct
            db.commit()


def run_comparison(comparison_id: int) -> dict:
    """完整执行一次对比，结果写入 DB 的 diffs 表。"""
    log.info("开始对比", comparison_id=comparison_id)
    t0 = time.time()

    # 标记 running
    with SessionLocal() as db:
        cmp = db.get(Comparison, comparison_id)
        if not cmp:
            log.error("任务不存在", cid=comparison_id)
            return {"status": "not_found"}
        cmp.status = ComparisonStatus.running
        cmp.started_at = datetime.now(timezone.utc)
        cmp.progress_phase = "starting"
        cmp.progress_pct = 0
        orig_path = cmp.orig_file.path
        scan_path = cmp.scan_file.path
        dpi = (cmp.settings_json or {}).get("dpi", settings.default_dpi)
        db.commit()

    try:
        # 导入 pipeline（worker 启动时延迟加载，避免 import 重量级模型阻塞 web）
        from pipeline.extract import extract_pdf_text
        from pipeline.ocr import ocr_pdf
        from pipeline.stamp_mask import detect_red_stamps
        from pipeline.stream import (
            build_stream_from_orig, build_stream_from_scan, build_doc_stream
        )
        from pipeline.diff import diff_documents
        from pipeline import cache as ocrcache
        from copy import deepcopy

        # 1) 抽取原件文字
        _update_progress(comparison_id, "extracting", 5, "抽取原件矢量文字")
        orig_pages = extract_pdf_text(orig_path)
        log.info("原件抽取完成", pages=len(orig_pages))

        # 2) OCR 扫描件（带缓存）
        _update_progress(comparison_id, "ocr", 10, "OCR 扫描件中（首次较慢）")
        cache_dir = settings.cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        fh = ocrcache.file_hash(scan_path)
        ocr_key = f"scan_{fh}_dpi{dpi}"
        cached = ocrcache.load(cache_dir, ocr_key)
        if cached is not None:
            scan_pages, stamp_regions_per_page = cached
            log.info("OCR 缓存命中", key=ocr_key)
            _update_progress(comparison_id, "ocr", 60, "OCR 缓存命中")
        else:
            scan_pages = ocr_pdf(scan_path, dpi=dpi)
            _update_progress(comparison_id, "stamp", 60, "检测红章")
            stamp_regions_per_page: dict[int, list] = {}
            for sp in scan_pages:
                boxes_px = detect_red_stamps(sp.image) if sp.image is not None else []
                scale = sp.img_width / sp.width
                stamp_regions_per_page[sp.page] = [
                    (b[0] / scale, b[1] / scale, b[2] / scale, b[3] / scale) for b in boxes_px
                ]
            # 缓存（去掉 image 节省空间）
            scan_pages_compact = []
            for sp in scan_pages:
                sp2 = deepcopy(sp)
                sp2.image = None
                scan_pages_compact.append(sp2)
            ocrcache.save(cache_dir, ocr_key, (scan_pages_compact, stamp_regions_per_page))

        # 3) 字符流 + diff
        _update_progress(comparison_id, "diffing", 75, "字符流对比中")
        orig_streams = [build_stream_from_orig(p) for p in orig_pages]
        scan_streams = [build_stream_from_scan(p) for p in scan_pages]
        orig_doc = build_doc_stream(orig_streams, skip_footer=True)
        scan_doc = build_doc_stream(scan_streams, skip_footer=True)

        diff_items = diff_documents(
            orig_doc, scan_doc,
            stamp_regions_per_page=stamp_regions_per_page,
        )
        log.info("diff 完成", count=len(diff_items))

        # 4) 持久化
        _update_progress(comparison_id, "saving", 90, "保存差异结果")
        _persist_results(comparison_id, diff_items)

        elapsed = time.time() - t0
        _update_progress(comparison_id, "done", 100, f"完成，耗时 {elapsed:.1f}s")

        with SessionLocal() as db:
            cmp = db.get(Comparison, comparison_id)
            cmp.status = ComparisonStatus.done
            cmp.completed_at = datetime.now(timezone.utc)
            db.commit()
        return {"status": "done", "elapsed": elapsed, "diffs": len(diff_items)}

    except Exception as exc:
        log.exception("对比失败", comparison_id=comparison_id)
        with SessionLocal() as db:
            cmp = db.get(Comparison, comparison_id)
            if cmp:
                cmp.status = ComparisonStatus.failed
                cmp.error_message = f"{type(exc).__name__}: {exc}"
                cmp.completed_at = datetime.now(timezone.utc)
                db.commit()
        publish_progress(comparison_id, "failed", 100, str(exc))
        raise


def _persist_results(comparison_id: int, diff_items: list) -> None:
    """把 pipeline 的 DiffItem 列表写入 DB，并计算 summary。"""
    summary = Counter()
    summary_real = 0
    summary_critical = 0

    NOISE_CATEGORIES = {"moved"}

    with SessionLocal() as db:
        # 删除可能存在的旧差异
        db.query(Diff).filter(Diff.comparison_id == comparison_id).delete()
        db.flush()

        for seq, d in enumerate(diff_items, start=1):
            row = Diff(
                comparison_id=comparison_id,
                seq_no=seq,
                category=DiffCategory(d.category),
                severity=DiffSeverity(d.severity),
                orig_page=d.orig_page,
                scan_page=d.scan_page,
                orig_text=d.orig_text or "",
                scan_text=d.scan_text or "",
                orig_bbox=list(d.orig_bbox) if d.orig_bbox else None,
                scan_bbox=list(d.scan_bbox) if d.scan_bbox else None,
                context=d.context or "",
                is_footer=bool(d.is_footer),
            )
            db.add(row)

            summary[d.category] += 1
            is_noise = d.category in NOISE_CATEGORIES or d.is_footer or d.severity == "info"
            if not is_noise:
                summary_real += 1
            if d.severity == "critical":
                summary_critical += 1
            if d.is_footer:
                summary["footer"] += 1

        cmp = db.get(Comparison, comparison_id)
        cmp.summary_json = {
            "total": sum(summary.values()) - summary.get("footer", 0) if False else int(sum(1 for _ in diff_items)),
            "real": summary_real,
            "critical": summary_critical,
            "replace": summary.get("replace", 0),
            "delete": summary.get("delete", 0),
            "insert": summary.get("insert", 0),
            "handwritten": summary.get("handwritten", 0),
            "stamp_covered": summary.get("stamp_covered", 0),
            "moved": summary.get("moved", 0),
            "footer": summary.get("footer", 0),
        }
        db.commit()

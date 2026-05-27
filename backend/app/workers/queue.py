"""Redis 连接 + RQ Queue 单例。"""
from __future__ import annotations
from functools import lru_cache
import redis
from rq import Queue
from app.core.config import settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=False)


@lru_cache
def get_queue() -> Queue:
    return Queue("comparisons", connection=get_redis(), default_timeout=60 * 30)


def enqueue_comparison(comparison_id: int) -> str:
    """把对比任务入队。"""
    from app.workers.compare_job import run_comparison
    job = get_queue().enqueue(run_comparison, comparison_id, job_id=f"cmp-{comparison_id}",
                              result_ttl=3600, failure_ttl=86400)
    return job.id


# ── 进度发布 ────────────────────────────────────────────
PROGRESS_CHANNEL_PREFIX = "comparison:progress:"


def publish_progress(comparison_id: int, phase: str, pct: int, message: str = "") -> None:
    """Worker 向 Redis pub/sub 发布进度，WebSocket 端订阅推送给前端。"""
    import json
    payload = json.dumps({"phase": phase, "pct": pct, "message": message}, ensure_ascii=False)
    get_redis().publish(f"{PROGRESS_CHANNEL_PREFIX}{comparison_id}", payload)

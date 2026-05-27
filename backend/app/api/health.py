"""健康检查与系统信息。"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.workers.queue import get_redis


router = APIRouter(tags=["健康检查"])


@router.get("/api/health", summary="健康检查")
def health(db: Session = Depends(get_db)):
    db_ok = False
    redis_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    try:
        get_redis().ping()
        redis_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    }

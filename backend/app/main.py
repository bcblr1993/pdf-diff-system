"""FastAPI 应用入口。"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.core.config import settings
from app.core.logging import setup_logging, get_logger


setup_logging()
log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("应用启动", env=settings.app_env, db=settings.postgres_host, redis=settings.redis_host)
    # 确保存储目录存在
    os.makedirs(settings.storage_dir, exist_ok=True)
    os.makedirs(os.path.join(settings.storage_dir, "pdfs"), exist_ok=True)
    os.makedirs(settings.cache_dir, exist_ok=True)
    # 自动 alembic upgrade head（开发期方便；生产可关掉）
    try:
        from alembic.config import Config
        from alembic import command
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(cfg, "head")
        log.info("数据库迁移已应用")
    except Exception as e:
        log.warning("alembic 迁移失败（可能是首次启动 PG 还没准备好）", error=str(e))
    # 创建初始管理员
    try:
        from app.services.bootstrap import ensure_initial_admin
        ensure_initial_admin()
    except Exception as e:
        log.warning("初始管理员创建失败", error=str(e))
    yield
    log.info("应用关闭")


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="1.0.0",
        description=(
            "**PDF 差异对比系统**\n\n"
            "上传一份原件（电子矢量 PDF）+ 一份扫描件（盖章扫描 PDF），系统自动 OCR + 字符流 diff + 高亮报告。\n\n"
            "## 使用流程\n"
            "1. `POST /api/auth/login` 拿 JWT，点右上 Authorize 输入 token\n"
            "2. `POST /api/comparisons` 上传两份 PDF\n"
            "3. （可选）WebSocket `/ws/comparisons/{id}/progress?token=<jwt>` 监听进度\n"
            "4. `GET /api/comparisons/{id}/diffs` 拉差异列表\n"
            "5. `PATCH /api/diffs/{id}` 标记审核动作（confirmed/ignored）\n"
            "6. `POST /api/comparisons/{id}/review/complete` 结束审核\n"
        ),
        lifespan=lifespan,
        openapi_tags=[
            {"name": "认证", "description": "登录与当前用户"},
            {"name": "用户管理", "description": "管理员创建/管理用户"},
            {"name": "对比任务", "description": "创建、查询、删除对比任务"},
            {"name": "差异", "description": "差异列表 + 审核动作"},
            {"name": "健康检查"},
        ],
    )

    # CORS（开发期全开，生产请收紧）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from app.api.auth import router as auth_router, users_router
    from app.api.comparisons import router as cmp_router
    from app.api.diffs import router as diffs_router
    from app.api.health import router as health_router
    from app.ws.progress import router as ws_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(cmp_router)
    app.include_router(diffs_router)
    app.include_router(ws_router)

    return app


app = create_app()

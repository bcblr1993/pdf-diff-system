"""WebSocket：对比任务进度推送。

订阅 Redis pub/sub 上的 `comparison:progress:{id}` 频道，把消息转发给浏览器。
认证：URL query ?token=<jwt> 或 Header Authorization。
"""
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from app.core.security import decode_token
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import Comparison, User
from app.workers.queue import get_redis, PROGRESS_CHANNEL_PREFIX


router = APIRouter()
log = get_logger("ws.progress")


@router.websocket("/ws/comparisons/{cid}/progress")
async def progress_ws(
    websocket: WebSocket,
    cid: int,
    token: str | None = Query(default=None),
):
    """握手时校验 JWT；连接后立即推一次当前状态，然后转发后续 Redis 消息。"""
    # 1) 认证
    if not token:
        # 兼容从 Authorization header 传入
        auth = websocket.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    payload = decode_token(token) if token else None
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="未认证")
        return

    user_id = int(payload.get("sub", 0)) if payload.get("sub") else 0
    with SessionLocal() as db:
        user = db.get(User, user_id) if user_id else None
        cmp = db.get(Comparison, cid)
        if not user or not user.is_active or not cmp:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="无权访问")
            return
        initial = {
            "phase": cmp.progress_phase or cmp.status.value,
            "pct": cmp.progress_pct,
            "status": cmp.status.value,
            "message": "",
        }

    await websocket.accept()
    await websocket.send_text(json.dumps(initial, ensure_ascii=False))

    # 如果任务已是终态，推送一次后就关闭
    if initial["status"] in ("done", "failed"):
        await websocket.close()
        return

    # 2) 订阅 Redis
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    channel = f"{PROGRESS_CHANNEL_PREFIX}{cid}"
    pubsub.subscribe(channel)

    try:
        # asyncio + 阻塞 redis 客户端：用 to_thread 包装
        loop = asyncio.get_event_loop()
        while True:
            # 非阻塞拉取（1s 超时）
            message = await loop.run_in_executor(
                None, lambda: pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            )
            if message is None:
                # 仍在连接，发个 ping
                try:
                    await asyncio.wait_for(websocket.send_text("​"), timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    break
                continue
            data = message.get("data")
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8", errors="ignore")
            if not data:
                continue
            await websocket.send_text(data)
            # 拿到终态后关闭
            try:
                obj = json.loads(data)
                if obj.get("phase") in ("done", "failed"):
                    break
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws 异常")
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass

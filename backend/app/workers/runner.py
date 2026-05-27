"""RQ Worker 入口。docker compose 用 `python -m app.workers.runner` 启动。"""
from __future__ import annotations
from rq import Worker
from app.core.logging import setup_logging, get_logger
from app.workers.queue import get_redis, get_queue


def main():
    setup_logging()
    log = get_logger("worker")
    queue = get_queue()
    log.info("Worker 启动", queue=queue.name, redis=queue.connection.connection_pool.connection_kwargs)
    worker = Worker([queue], connection=get_redis())
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()

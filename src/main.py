"""たんぼアドバイザー - FastAPI アプリケーション"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.models.database import init_db
from src.api.webhook import router as webhook_router
from src.jobs.scheduler import scheduler, setup_jobs
from config.settings import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理"""
    # 起動時
    logger.info("Initializing tanbo-adviser...")
    init_db()
    setup_jobs()
    scheduler.start()
    logger.info("tanbo-adviser started successfully")

    yield

    # 終了時
    scheduler.shutdown()
    logger.info("tanbo-adviser shutdown complete")


app = FastAPI(
    title="たんぼアドバイザー",
    description="水稲農家向け圃場環境モニタリング＋行動提案システム",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)


@app.get("/")
async def root():
    return {
        "name": "たんぼアドバイザー",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}

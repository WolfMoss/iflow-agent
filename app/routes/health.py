# -*- coding: utf-8 -*-
"""健康检查与就绪探针。"""
import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from core.config import settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    """存活探针：进程在即可。"""
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def ready() -> dict:
    """就绪探针：可选的 iFlow 连接检查，当前仅返回 ok。"""
    # 可选：用 iflow_sdk 或 websocket 探测 settings.iflow_ws_url
    return {"status": "ok", "iflow_url": settings.iflow_ws_url}

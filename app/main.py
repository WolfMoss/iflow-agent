# -*- coding: utf-8 -*-
"""FastAPI 应用入口：路由、静态资源、CORS。"""
import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.iflow_runner import start_iflow_process, stop_iflow_process
from app.routes import chat, health, telegram_webhook
from app.routes.telegram_webhook import run_telegram_long_polling
from channels.qq import start_qq_bot_in_background

app = FastAPI(
    title="iFlow Agent Gateway",
    description="WebUI 与多通道接入，模型/Skill/MCP 由 iFlow CLI 原生负责",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(telegram_webhook.router)

# 静态资源：Web UI
web_dir = Path(__file__).resolve().parent.parent / "web"
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")


def _configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _ensure_default_workspace() -> None:
    """在用户目录下创建默认工作区目录，并将进程 cwd 切到该目录。
    这样 iFlow 子进程继承的 cwd、SDK IFlowOptions 的默认 cwd（os.getcwd()）
    以及 protocol 参数里的 cwd 全部指向同一个工作区，不再受 run.py 启动目录影响。
    """
    path = Path(settings.iflow_default_workspace_path())
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    logging.getLogger(__name__).info("默认工作目录（已 chdir）: %s", path)


@app.on_event("startup")
async def startup() -> None:
    _configure_logging()
    _ensure_default_workspace()
    proc = start_iflow_process()
    if proc is not None:
        app.state.iflow_process = proc
        await asyncio.sleep(2)
    if settings.telegram_enabled() and not settings.telegram_use_webhook:
        asyncio.create_task(run_telegram_long_polling())
    if settings.qq_enabled():
        start_qq_bot_in_background()


@app.on_event("shutdown")
async def shutdown() -> None:
    proc = getattr(app.state, "iflow_process", None)
    stop_iflow_process(proc)
    if proc is not None:
        logging.getLogger(__name__).info("已停止自动启动的 iFlow 进程")

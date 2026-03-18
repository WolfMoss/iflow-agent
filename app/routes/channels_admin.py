# -*- coding: utf-8 -*-
"""
渠道配置管理（保存修改 .env 并重启服务以生效）。

目前支持：
- Telegram：TELEGRAM_BOT_TOKEN / TELEGRAM_ALLOW_FROM / TELEGRAM_USE_WEBHOOK / TELEGRAM_PROXY / TELEGRAM_TIMEOUT
- QQ：QQ_APP_ID / QQ_APP_SECRET / QQ_SANDBOX
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels-admin"])


class ChannelsConfigPayload(BaseModel):
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_ALLOW_FROM: str = Field(default="")
    TELEGRAM_USE_WEBHOOK: bool = Field(default=False)
    TELEGRAM_PROXY: str = Field(default="")
    TELEGRAM_TIMEOUT: float = Field(default=60.0)

    QQ_APP_ID: str = Field(default="")
    QQ_APP_SECRET: str = Field(default="")
    QQ_SANDBOX: bool = Field(default=True)


def _project_root() -> Path:
    # app/routes/channels_admin.py -> app/routes -> app -> project root
    return Path(__file__).resolve().parents[2]


def _env_path() -> Path:
    return _project_root() / ".env"


def _write_env_kv(env_path: Path, updates: dict[str, str]) -> None:
    """
    以 LF 写回 .env：
    - 覆盖：匹配 `^KEY=` 或 `^#KEY=`（含可选空格）时替换为 `KEY=value`
    - 追加：未出现的 key，追加到文件末尾
    """
    existing = ""
    if env_path.exists():
        existing = env_path.read_text(encoding="utf-8", errors="ignore")

    lines = existing.splitlines()
    updated: set[str] = set()
    out_lines: list[str] = []

    for line in lines:
        replaced = False
        for key, value in updates.items():
            pattern = rf"^\s*(?:#\s*)?{re.escape(key)}\s*="
            if re.match(pattern, line):
                out_lines.append(f"{key}={value}")
                updated.add(key)
                replaced = True
                break
        if not replaced:
            out_lines.append(line)

    for key, value in updates.items():
        if key not in updated:
            out_lines.append(f"{key}={value}")

    # 强制 LF
    content = "\n".join(out_lines).rstrip("\n") + "\n"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    with open(env_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def _restart_gateway_service() -> None:
    """
    后台线程执行：
    - 切回项目根目录，确保重新读取 .env
    - 用 execv 重新执行 run.py（重启 FastAPI 网关与 iFlow 自动拉起逻辑）
    """
    try:
        root = _project_root()
        os.chdir(root)
        # 给当前请求返回一点时间（避免连接提前断开）
        time.sleep(0.6)
        # 在 uvicorn --reload 模式下直接 execv 可能导致进程状态异常。
        # 这里通过“触发文件变更 + 退出当前子进程”，让 reloader 自动拉起新进程。
        try:
            (root / "run.py").touch()
        except Exception:
            pass
        os._exit(0)
    except Exception as e:
        # execv 失败时不影响请求已返回；尽量记录日志
        logger.exception("重启网关失败: %s", e)


@router.get("/config")
async def get_channels_config() -> dict[str, Any]:
    """返回当前 settings（用于前端回填）。"""
    return {
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
        "TELEGRAM_ALLOW_FROM": settings.telegram_allow_from,
        "TELEGRAM_USE_WEBHOOK": settings.telegram_use_webhook,
        "TELEGRAM_PROXY": settings.telegram_proxy,
        "TELEGRAM_TIMEOUT": settings.telegram_timeout,
        "QQ_APP_ID": settings.qq_app_id,
        "QQ_APP_SECRET": settings.qq_app_secret,
        "QQ_SANDBOX": settings.qq_sandbox,
    }


@router.post("/config/save-restart")
async def save_channels_config_and_restart(payload: ChannelsConfigPayload) -> dict[str, Any]:
    """
    写回 .env，然后重启网关服务以生效。
    """
    env_path = _env_path()
    updates: dict[str, str] = {
        "TELEGRAM_BOT_TOKEN": payload.TELEGRAM_BOT_TOKEN or "",
        "TELEGRAM_ALLOW_FROM": payload.TELEGRAM_ALLOW_FROM or "",
        "TELEGRAM_USE_WEBHOOK": "true" if payload.TELEGRAM_USE_WEBHOOK else "false",
        "TELEGRAM_PROXY": payload.TELEGRAM_PROXY or "",
        "TELEGRAM_TIMEOUT": str(payload.TELEGRAM_TIMEOUT),
        "QQ_APP_ID": payload.QQ_APP_ID or "",
        "QQ_APP_SECRET": payload.QQ_APP_SECRET or "",
        "QQ_SANDBOX": "true" if payload.QQ_SANDBOX else "false",
    }

    try:
        _write_env_kv(env_path, updates)
    except Exception as e:
        logger.exception("写回 .env 失败: %s", e)
        return {"ok": False, "error": f"write env failed: {e}"}

    # 异步重启，避免请求被阻塞
    threading.Thread(target=_restart_gateway_service, name="channels-restart", daemon=True).start()
    return {"ok": True, "restarting": True}


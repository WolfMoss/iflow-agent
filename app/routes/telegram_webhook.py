# -*- coding: utf-8 -*-
"""
Telegram 渠道：Webhook（需公网 HTTPS）或 Long Polling（本地无需域名）。
参考 nanobot：默认用 Long Polling，本机联网即可与机器人对话；可选 Webhook 部署到服务器。
"""
import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.chat_service import ensure_new_session, ensure_session, is_new_session_command, stream_reply
from channels.telegram import TelegramChannelAdapter, get_updates
from core.config import settings

router = APIRouter(prefix="/channels", tags=["telegram"])
logger = logging.getLogger(__name__)

_telegram_adapter = TelegramChannelAdapter()


async def _handle_telegram_event(event: Any) -> None:
    """后台：确保会话、流式回复、通过 Telegram 适配器回发。识别 /new 则新建会话并回复提示。"""
    try:
        if is_new_session_command(event.message):
            info = await ensure_new_session(
                channel=event.channel,
                channel_user_id=event.channel_user_id,
                channel_session_id=event.channel_session_id,
            )

            async def new_session_reply():
                yield {"type": "assistant_chunk", "text": "已新建会话，可以继续发消息。"}
                yield {"type": "task_finish", "stop_reason": ""}

            await _telegram_adapter.send_stream(info, new_session_reply())
            return

        info = await ensure_session(
            channel=event.channel,
            channel_user_id=event.channel_user_id,
            channel_session_id=event.channel_session_id,
        )

        async def event_stream():
            async for e in stream_reply(
                message=event.message,
                session_id=info.session_id,
                cwd=settings.iflow_default_workspace_path(),
            ):
                yield e

        await _telegram_adapter.send_stream(info, event_stream())
    except Exception as e:
        logger.exception("Telegram 处理异常: %s", e)


@router.post("/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    """
    Telegram Bot Webhook 入口。
    配置 Bot 时请将 Webhook URL 设为: https://你的域名/channels/telegram
    需 HTTPS；本地调试可用 ngrok 等暴露端口。
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(content={"ok": True}, status_code=200)

    if not settings.telegram_enabled():
        return JSONResponse(content={"ok": True}, status_code=200)

    event = await _telegram_adapter.parse_request(body)
    if not event:
        return JSONResponse(content={"ok": True}, status_code=200)

    if not settings.telegram_user_allowed(event.channel_user_id):
        logger.info("Telegram 拒绝未授权用户: %s", event.channel_user_id)
        return JSONResponse(content={"ok": True}, status_code=200)

    if (event.message or "").strip() in ("", "(空消息)"):
        return JSONResponse(content={"ok": True}, status_code=200)

    asyncio.create_task(_handle_telegram_event(event))
    return JSONResponse(content={"ok": True}, status_code=200)


async def run_telegram_long_polling() -> None:
    """
    Long Polling 循环：本机主动向 Telegram 拉取新消息，无需公网 IP 或域名。
    本地电脑联网即可使用，与 nanobot 行为一致。
    """
    if not settings.telegram_enabled() or settings.telegram_use_webhook:
        return
    logger.info("Telegram Long Polling 已启动，本地可直接与机器人对话，无需域名")
    offset = 0
    while True:
        try:
            updates, offset = await get_updates(offset, timeout=25)
            for raw in updates:
                event = await _telegram_adapter.parse_request(raw)
                if not event:
                    continue
                if not settings.telegram_user_allowed(event.channel_user_id):
                    continue
                if (event.message or "").strip() in ("", "(空消息)"):
                    continue
                asyncio.create_task(_handle_telegram_event(event))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Telegram Long Polling 异常: %s", e)
            await asyncio.sleep(5)

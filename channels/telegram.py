# -*- coding: utf-8 -*-
"""
Telegram 渠道适配器。
参考 nanobot：Bot Token、allowFrom 白名单；Webhook 接收更新，聚合回复后通过 Bot API 发送。
单条消息最长 4096 字符，过长时分段发送。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

import httpx

from channels.base import ChannelAdapter, InboundEvent
from core.config import settings
from core.session import SessionInfo

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096
LONG_POLL_TIMEOUT = 25
TYPING_ACTION_INTERVAL = 4


def _extract_message_from_update(raw: dict) -> tuple[str, str, str] | None:
    """
    从 Telegram Update 中提取 chat_id, user_id, text。
    支持 message 与 edited_message。
    返回 (chat_id, user_id, text) 或 None。
    """
    msg = raw.get("message") or raw.get("edited_message")
    if not msg or not isinstance(msg, dict):
        return None
    chat = msg.get("chat")
    from_user = msg.get("from")
    if not chat or not from_user:
        return None
    chat_id = str(chat.get("id", ""))
    user_id = str(from_user.get("id", ""))
    text = (msg.get("text") or msg.get("caption") or "").strip()
    return (chat_id, user_id, text)


class TelegramChannelAdapter(ChannelAdapter):
    """Telegram Bot 渠道：解析 Webhook Update，聚合流式回复后通过 sendMessage 回发。"""

    @property
    def channel_id(self) -> str:
        return "telegram"

    async def parse_request(self, raw: Any) -> InboundEvent | None:
        if not isinstance(raw, dict):
            return None
        parsed = _extract_message_from_update(raw)
        if not parsed:
            return None
        chat_id, user_id, text = parsed
        if not chat_id or not user_id:
            return None
        return InboundEvent(
            channel=self.channel_id,
            channel_user_id=user_id,
            channel_session_id=chat_id,
            message=text or "(空消息)",
            raw=raw,
        )

    async def send_chat_action(self, chat_id: str, action: str = "typing") -> None:
        """发送聊天状态（如「正在输入」），在对话标题处显示。action 约 5 秒后失效，需定期重发。"""
        token = settings.telegram_bot_token.strip()
        if not token:
            return
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendChatAction"
        timeout = httpx.Timeout(settings.telegram_timeout)
        proxy = settings.telegram_proxy.strip() or None
        try:
            async with httpx.AsyncClient(timeout=timeout, proxy=proxy) as client:
                await client.post(
                    url,
                    json={"chat_id": chat_id, "action": action},
                )
        except Exception as e:
            logger.debug("sendChatAction 失败: %s", e)

    async def send_stream(
        self,
        session_info: SessionInfo,
        events: AsyncIterator[dict],
    ) -> None:
        buffer: list[str] = []
        current = []
        current_len = 0
        chat_id = session_info.channel_session_id

        typing_task: asyncio.Task | None = None

        async def _keep_typing() -> None:
            while True:
                await self.send_chat_action(chat_id, "typing")
                await asyncio.sleep(TYPING_ACTION_INTERVAL)

        try:
            typing_task = asyncio.create_task(_keep_typing())
        except Exception:
            pass

        try:
            async for event in events:
                if event.get("type") == "assistant_chunk":
                    chunk = event.get("text") or ""
                    if not chunk:
                        continue
                    for char in chunk:
                        if current_len >= MAX_MESSAGE_LENGTH:
                            buffer.append("".join(current))
                            current = []
                            current_len = 0
                        current.append(char)
                        current_len += 1
                elif event.get("type") == "task_finish":
                    break
                elif event.get("type") == "error":
                    buffer.append(event.get("message", "请求出错"))
                    break
        finally:
            if typing_task is not None and not typing_task.done():
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass

        if current:
            buffer.append("".join(current))

        token = settings.telegram_bot_token.strip()
        if not token:
            logger.warning("Telegram token 未配置，无法回发")
            return
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

        timeout = httpx.Timeout(settings.telegram_timeout)
        proxy = settings.telegram_proxy.strip() or None
        for i, part in enumerate(buffer):
            if not part.strip():
                continue
            try:
                async with httpx.AsyncClient(timeout=timeout, proxy=proxy) as client:
                    r = await client.post(
                        url,
                        json={"chat_id": chat_id, "text": part},
                    )
                    if r.status_code != 200:
                        logger.warning("Telegram sendMessage 失败: %s %s", r.status_code, r.text)
            except Exception as e:
                logger.exception("Telegram 发送异常: %s", e)


async def get_updates(offset: int, timeout: int = LONG_POLL_TIMEOUT) -> tuple[list[dict], int]:
    """
    Long Polling：向 Telegram 拉取新消息，无需公网或域名。
    返回 (本批 updates 列表, 下一轮应用的 offset)。
    """
    token = settings.telegram_bot_token.strip()
    if not token:
        return [], offset
    url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
    next_offset = offset
    tg_timeout = httpx.Timeout(max(settings.telegram_timeout, float(timeout + 10)))
    proxy = settings.telegram_proxy.strip() or None
    try:
        async with httpx.AsyncClient(timeout=tg_timeout, proxy=proxy) as client:
            r = await client.get(
                url,
                params={"offset": offset, "timeout": timeout},
            )
            if r.status_code != 200:
                return [], offset
            data = r.json()
            if not data.get("ok") or "result" not in data:
                return [], offset
            result = data["result"]
            if not result:
                return [], offset
            for u in result:
                next_offset = max(next_offset, int(u.get("update_id", 0)) + 1)
            return result, next_offset
    except Exception as e:
        logger.debug("getUpdates 请求异常: %s", e)
        return [], offset

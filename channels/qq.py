# -*- coding: utf-8 -*-
"""
QQ 渠道接入（腾讯官方机器人平台 botpy SDK）。

设计目标：
- 参考 D:\\codes\\py-qqbot 的接入方式（botpy Client 事件回调）
- 不拆分多个 py：本文件同时包含 botpy 启动、事件处理、会话映射、/new 逻辑
- 网关内直接调用 stream_reply 与会话服务，不走 REST 回环
"""

from __future__ import annotations

import asyncio
import logging
import threading

from app.services.chat_service import (
    ensure_new_session,
    ensure_session,
    is_new_session_command,
    stream_reply,
)
from core.config import settings

logger = logging.getLogger(__name__)


def _clean_content(text: str) -> str:
    """去除 QQ 频道里常见的 mention 标签，清理首尾空白。"""
    if not text:
        return ""
    # QQ 频道 mention 形如：<@!BOTID> 或 <@BOTID>
    import re

    text = re.sub(r"<@!?\d+>", "", text)
    return text.strip()


async def _collect_reply_text(
    user_text: str,
    session_id: str,
) -> str:
    """调用 iFlow 流式事件并拼接最终文本。"""
    parts: list[str] = []
    async for e in stream_reply(
        message=user_text,
        session_id=session_id,
        cwd=settings.iflow_default_workspace_path(),
    ):
        t = e.get("type")
        if t == "assistant_chunk":
            chunk = e.get("text") or ""
            if chunk:
                parts.append(str(chunk))
        elif t == "task_finish":
            break
        elif t == "error":
            return f"请求出错：{e.get('message') or ''}".strip()
    final = "".join(parts).strip()
    return final or "(无文本回复)"


def start_qq_bot_in_background() -> None:
    """
    按环境变量启动 QQ Bot（后台线程，不阻塞 FastAPI）。

    需要在 .env 中配置：
    - QQ_APP_ID
    - QQ_APP_SECRET
    - QQ_SANDBOX（可选，默认 true）
    """
    if not settings.qq_enabled():
        return

    try:
        import botpy
        from botpy.message import DirectMessage, GroupMessage, Message
    except Exception as e:
        logger.warning("QQ 渠道未安装 qq-botpy，无法启动（pip install qq-botpy）：%s", e)
        return

    class QQBot(botpy.Client):
        async def on_ready(self):
            logger.info("QQ Bot 已启动，AppID=%s sandbox=%s", settings.qq_app_id, settings.qq_sandbox)

        async def _handle_text(
            self,
            raw_text: str,
            source: str,
            channel_user_id: str,
            channel_session_id: str,
        ) -> str:
            text = _clean_content(raw_text)
            if is_new_session_command(text):
                info = await ensure_new_session(
                    channel="qq",
                    channel_user_id=channel_user_id,
                    channel_session_id=channel_session_id,
                )
                return "已新建会话，可以继续发消息。"

            info = await ensure_session(
                channel="qq",
                channel_user_id=channel_user_id,
                channel_session_id=channel_session_id,
            )
            return await _collect_reply_text(
                user_text=text or "(空消息)",
                session_id=info.session_id,
            )

        # ──────────────────────────────
        # 频道消息（被 @）
        # ──────────────────────────────
        async def on_at_message_create(self, message: Message):
            try:
                user_id = str(getattr(message.author, "id", "") or getattr(message.author, "username", ""))
                # 频道会话建议按 channel_id 固定（同一频道同一会话）
                channel_id = str(getattr(message, "channel_id", "") or "")
                guild_id = str(getattr(message, "guild_id", "") or "")
                sess = f"guild:{guild_id}:{channel_id}" if (guild_id or channel_id) else "guild"
                reply = await self._handle_text(message.content or "", "guild", user_id or "unknown", sess)
                await message.reply(content=reply)
            except Exception as e:
                logger.exception("QQ guild @ 消息处理异常: %s", e)

        # ──────────────────────────────
        # C2C（好友私聊）
        # ──────────────────────────────
        async def on_c2c_message_create(self, message: GroupMessage):
            try:
                user_openid = str(getattr(message.author, "user_openid", "") or "unknown")
                sess = f"c2c:{user_openid}"
                reply = await self._handle_text(message.content or "", "c2c", user_openid, sess)
                await message.reply(content=reply)
            except Exception as e:
                logger.exception("QQ c2c 消息处理异常: %s", e)

        # ──────────────────────────────
        # 群聊（被 @）
        # ──────────────────────────────
        async def on_group_at_message_create(self, message: GroupMessage):
            try:
                group_openid = str(getattr(message, "group_openid", "") or "unknown")
                member_openid = str(getattr(message.author, "member_openid", "") or "unknown")
                sess = f"group:{group_openid}"
                reply = await self._handle_text(message.content or "", "group", member_openid, sess)
                await message.reply(content=reply)
            except Exception as e:
                logger.exception("QQ group @ 消息处理异常: %s", e)

        # ──────────────────────────────
        # 频道私信
        # ──────────────────────────────
        async def on_direct_message_create(self, message: DirectMessage):
            try:
                author = getattr(message, "author", None)
                user_id = str(getattr(author, "id", "") or getattr(author, "username", "") or "unknown")
                guild_id = str(getattr(message, "guild_id", "") or "")
                sess = f"direct:{guild_id}:{user_id}" if guild_id else f"direct:{user_id}"
                reply = await self._handle_text(message.content or "", "direct", user_id, sess)
                # DirectMessage 没有 reply，使用 API 回发
                await self.api.post_dms(
                    guild_id=message.guild_id,
                    content=reply,
                    msg_id=message.id,
                )
            except Exception as e:
                logger.exception("QQ direct 消息处理异常: %s", e)

    def _thread_main() -> None:
        # 为 qq-botpy 线程创建并设置事件循环，避免 RuntimeError: no current event loop
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            intents = botpy.Intents(
                public_guild_messages=True,  # 频道 @ 消息
                public_messages=True,  # C2C / 群
                direct_message=True,  # 频道私信
                guild_messages=True,  # 全量频道消息（私域机器人）
            )
            client = QQBot(intents=intents, is_sandbox=settings.qq_sandbox)
            client.run(appid=settings.qq_app_id, secret=settings.qq_app_secret)
        finally:
            try:
                loop.close()
            except Exception:
                pass

    t = threading.Thread(target=_thread_main, name="qq-botpy", daemon=True)
    t.start()
    logger.info("QQ Bot 后台线程已启动")


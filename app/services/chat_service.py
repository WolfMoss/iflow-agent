# -*- coding: utf-8 -*-
"""聊天服务：会话解析与桥接调用。"""
from __future__ import annotations

from typing import AsyncIterator

from core.iflow_bridge import stream_chat
from core.session import SessionInfo, SessionStore, get_session_store
from core.config import settings


_session_store: SessionStore | None = None


def get_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = get_session_store(settings.session_store_url)
    return _session_store


async def ensure_session(
    channel: str,
    channel_user_id: str,
    channel_session_id: str,
    session_id: str | None = None,
) -> SessionInfo:
    """获取或创建会话。"""
    store = get_store()
    if session_id:
        info = store.get(session_id)
        if info:
            return info
    return store.create(
        channel=channel,
        channel_user_id=channel_user_id,
        channel_session_id=channel_session_id,
        session_id=session_id,
    )


async def stream_reply(
    message: str,
    session_id: str | None = None,
    timeout: float | None = None,
) -> AsyncIterator[dict]:
    """发送消息并流式返回事件。"""
    async for event in stream_chat(
        message=message,
        session_id=session_id,
        timeout=timeout,
    ):
        yield event

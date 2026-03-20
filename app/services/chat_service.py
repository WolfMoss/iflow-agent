# -*- coding: utf-8 -*-
"""聊天服务：会话解析与桥接调用。"""
from __future__ import annotations

import hashlib
import uuid
from typing import AsyncIterator

from core.iflow_bridge import stream_chat
from core.message_trace import log_inbound
from core.session import SessionInfo, SessionStore, get_session_store
from core.config import settings


_session_store: SessionStore | None = None

NEW_SESSION_CMD = "/new"


def is_new_session_command(message: str) -> bool:
    """是否为由用户触发的「新建会话」指令（如 /new）。"""
    return (message or "").strip().lower() == NEW_SESSION_CMD


def get_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = get_session_store(settings.session_store_url)
    return _session_store


def _stable_session_id(channel: str, channel_user_id: str, channel_session_id: str) -> str:
    """由渠道+用户+会话生成固定 session_id，重启服务后同一聊天仍为同一会话。"""
    raw = f"{channel}:{channel_user_id}:{channel_session_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def ensure_session(
    channel: str,
    channel_user_id: str,
    channel_session_id: str,
    session_id: str | None = None,
) -> SessionInfo:
    """获取或创建会话。渠道（如 Telegram）未传 session_id 时先查 override，再回退到稳定 id；Web 未传时用随机 id。"""
    store = get_store()
    if session_id:
        info = store.get(session_id)
        if info:
            return info
    if session_id is None and channel != "web" and (channel_user_id or channel_session_id):
        session_id = store.get_current_session_id(
            channel, channel_user_id, channel_session_id
        ) or _stable_session_id(channel, channel_user_id, channel_session_id)
    return store.create(
        channel=channel,
        channel_user_id=channel_user_id,
        channel_session_id=channel_session_id,
        session_id=session_id,
    )


async def ensure_new_session(
    channel: str,
    channel_user_id: str,
    channel_session_id: str,
) -> SessionInfo:
    """新建会话并设为该渠道用户的当前会话（覆盖稳定 id），用于 /new 指令。"""
    store = get_store()
    new_id = str(uuid.uuid4())
    store.set_current_session_id(channel, channel_user_id, channel_session_id, new_id)
    return store.create(
        channel=channel,
        channel_user_id=channel_user_id,
        channel_session_id=channel_session_id,
        session_id=new_id,
    )


async def stream_reply(
    message: str,
    session_id: str | None = None,
    timeout: float | None = None,
    cwd: str | None = None,
    *,
    trace_channel: str | None = None,
    trace_channel_user_id: str | None = None,
    trace_channel_session_id: str | None = None,
) -> AsyncIterator[dict]:
    """发送消息并流式返回事件。cwd 可选，指定本次请求的 iFlow 工作目录。

    传入 trace_* 时在首包前打印入站文案（与渠道日志对齐）。
    """
    if trace_channel is not None:
        log_inbound(
            trace_channel,
            trace_channel_user_id or "",
            trace_channel_session_id or "",
            message,
        )
    async for event in stream_chat(
        message=message,
        session_id=session_id,
        timeout=timeout,
        cwd=cwd,
    ):
        yield event

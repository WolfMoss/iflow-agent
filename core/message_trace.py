# -*- coding: utf-8 -*-
"""关键消息追踪：入站用户文案与 iFlow 产出，供运维排查；不包含 httpx 等底层 HTTP 心跳。"""
from __future__ import annotations

import logging

_logger = logging.getLogger("iflow_agent.message")


def log_inbound(
    channel: str,
    channel_user_id: str,
    channel_session_id: str,
    message: str,
    *,
    max_chars: int = 8000,
) -> None:
    """记录任意渠道收到的用户消息。"""
    text = message
    if len(text) > max_chars:
        text = f"{text[:max_chars]}…(共 {len(message)} 字，已截断)"
    _logger.info(
        "[入站] channel=%s user=%s session=%s | %s",
        channel,
        channel_user_id,
        channel_session_id,
        text,
    )


def log_iflow_assistant_complete(session_id: str | None, text: str, *, max_chars: int = 16000) -> None:
    """一轮对话结束时汇总助手全文（避免按 chunk 刷屏）。"""
    if not text:
        return
    body = text if len(text) <= max_chars else f"{text[:max_chars]}…(共 {len(text)} 字，已截断)"
    _logger.info("[iFlow 回复] session=%s | %s", session_id or "(none)", body)


def log_iflow_tool(tool_name: object, status: str, agent_id: object) -> None:
    _logger.info(
        "[iFlow 工具] name=%s status=%s agent_id=%s",
        tool_name,
        status,
        agent_id,
    )


def log_iflow_plan(entry_count: int) -> None:
    _logger.info("[iFlow 计划] entries=%s", entry_count)


def log_iflow_task_finish(stop_reason: str) -> None:
    _logger.info("[iFlow 结束] stop_reason=%s", stop_reason)


def log_iflow_error(message: str) -> None:
    _logger.info("[iFlow 错误] %s", message)

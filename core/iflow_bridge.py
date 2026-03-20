# -*- coding: utf-8 -*-
"""IFlow SDK 桥接：连接已启动的 iFlow 进程，发送消息并流式返回事件。"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from iflow_sdk import (
    AssistantMessage,
    IFlowClient,
    IFlowOptions,
    PlanMessage,
    TaskFinishMessage,
    ToolCallMessage,
)

from core.config import settings
from core.message_trace import (
    log_iflow_assistant_complete,
    log_iflow_error,
    log_iflow_plan,
    log_iflow_task_finish,
    log_iflow_tool,
)

logger = logging.getLogger(__name__)


def _options(
    session_id: str | None = None,
    timeout: float | None = None,
    cwd: str | None = None,
) -> IFlowOptions:
    kwargs: dict = {
        "url": settings.iflow_ws_url,
        "auto_start_process": False,
        "timeout": timeout or settings.iflow_timeout,
        "session_id": session_id,
    }
    if cwd and cwd.strip():
        kwargs["cwd"] = cwd.strip()
    opts = IFlowOptions(**kwargs)
    logger.debug("IFlowOptions: cwd=%s, session_id=%s", opts.cwd, opts.session_id)
    return opts


async def stream_chat(
    message: str,
    session_id: str | None = None,
    timeout: float | None = None,
    cwd: str | None = None,
) -> AsyncIterator[dict]:
    """
    向 iFlow 发送一条消息，并流式产出标准化事件字典。
    事件类型: assistant_chunk, tool_call, plan, task_finish, error。
    cwd 可指定本次对话的工作目录，不传则使用 iFlow 默认（进程当前目录）。
    """
    options = _options(session_id=session_id, timeout=timeout, cwd=cwd)
    assistant_parts: list[str] = []
    try:
        async with IFlowClient(options) as client:
            await client.send_message(message)
            async for msg in client.receive_messages():
                if isinstance(msg, AssistantMessage):
                    text = getattr(msg.chunk, "text", "") or ""
                    event = {
                        "type": "assistant_chunk",
                        "text": text,
                        "agent_id": getattr(msg, "agent_id", None),
                    }
                    if text:
                        assistant_parts.append(text)
                    yield event
                elif isinstance(msg, ToolCallMessage):
                    status = str(getattr(msg, "status", ""))
                    tool_name = getattr(msg, "tool_name", None)
                    aid = (
                        getattr(msg.agent_info, "agent_id", None)
                        if getattr(msg, "agent_info", None)
                        else None
                    )
                    event = {
                        "type": "tool_call",
                        "status": status,
                        "tool_name": tool_name,
                        "agent_id": aid,
                    }
                    log_iflow_tool(tool_name, status, aid)
                    yield event
                elif isinstance(msg, PlanMessage):
                    entries = [
                        {
                            "content": getattr(e, "content", ""),
                            "priority": getattr(e, "priority", ""),
                            "status": getattr(e, "status", ""),
                        }
                        for e in getattr(msg, "entries", [])
                    ]
                    event = {"type": "plan", "entries": entries}
                    log_iflow_plan(len(entries))
                    yield event
                elif isinstance(msg, TaskFinishMessage):
                    stop_reason = str(getattr(msg, "stop_reason", ""))
                    event = {"type": "task_finish", "stop_reason": stop_reason}
                    log_iflow_assistant_complete(session_id, "".join(assistant_parts))
                    log_iflow_task_finish(stop_reason)
                    yield event
                    return
    except Exception as e:
        logger.exception("iflow stream_chat error")
        if assistant_parts:
            log_iflow_assistant_complete(session_id, "".join(assistant_parts))
        log_iflow_error(str(e))
        yield {"type": "error", "message": str(e)}


def format_event_for_sse(event: dict) -> str:
    """将事件字典转为 SSE 行（data 为单行 JSON）。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

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

logger = logging.getLogger(__name__)


def _options(session_id: str | None = None, timeout: float | None = None) -> IFlowOptions:
    return IFlowOptions(
        url=settings.iflow_ws_url,
        auto_start_process=False,
        timeout=timeout or settings.iflow_timeout,
        session_id=session_id,
    )


async def stream_chat(
    message: str,
    session_id: str | None = None,
    timeout: float | None = None,
) -> AsyncIterator[dict]:
    """
    向 iFlow 发送一条消息，并流式产出标准化事件字典。
    事件类型: assistant_chunk, tool_call, plan, task_finish, error。
    """
    options = _options(session_id=session_id, timeout=timeout)
    try:
        async with IFlowClient(options) as client:
            await client.send_message(message)
            async for msg in client.receive_messages():
                if isinstance(msg, AssistantMessage):
                    yield {
                        "type": "assistant_chunk",
                        "text": getattr(msg.chunk, "text", "") or "",
                        "agent_id": getattr(msg, "agent_id", None),
                    }
                elif isinstance(msg, ToolCallMessage):
                    yield {
                        "type": "tool_call",
                        "status": str(getattr(msg, "status", "")),
                        "tool_name": getattr(msg, "tool_name", None),
                        "agent_id": getattr(msg.agent_info, "agent_id", None) if getattr(msg, "agent_info", None) else None,
                    }
                elif isinstance(msg, PlanMessage):
                    entries = [
                        {
                            "content": getattr(e, "content", ""),
                            "priority": getattr(e, "priority", ""),
                            "status": getattr(e, "status", ""),
                        }
                        for e in getattr(msg, "entries", [])
                    ]
                    yield {"type": "plan", "entries": entries}
                elif isinstance(msg, TaskFinishMessage):
                    yield {
                        "type": "task_finish",
                        "stop_reason": str(getattr(msg, "stop_reason", "")),
                    }
                    return
    except Exception as e:
        logger.exception("iflow stream_chat error")
        yield {"type": "error", "message": str(e)}


def format_event_for_sse(event: dict) -> str:
    """将事件字典转为 SSE 行（data 为单行 JSON）。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

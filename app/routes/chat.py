# -*- coding: utf-8 -*-
"""聊天 API：会话与流式回复。"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.chat_service import ensure_session, get_store, stream_reply
from core.iflow_bridge import format_event_for_sse

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """聊天请求体。"""

    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，不传则新建")
    channel: str = Field(default="web", description="渠道标识")
    channel_user_id: str = Field(default="default", description="渠道侧用户 ID")
    channel_session_id: Optional[str] = Field(None, description="渠道侧会话 ID，不传则用 session_id")


class CreateSessionRequest(BaseModel):
    """创建会话请求。"""

    channel: str = "web"
    channel_user_id: str = "default"
    channel_session_id: Optional[str] = None


@router.post("/sessions")
async def create_session(
    body: CreateSessionRequest,
    request: Request,
) -> dict:
    """创建新会话，返回 session_id。"""
    info = await ensure_session(
        channel=body.channel,
        channel_user_id=body.channel_user_id,
        channel_session_id=body.channel_session_id or "",
    )
    return {"session_id": info.session_id}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """获取会话信息。"""
    store = get_store()
    info = store.get(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": info.session_id,
        "channel": info.channel,
        "channel_user_id": info.channel_user_id,
        "channel_session_id": info.channel_session_id,
        "created_at": info.created_at,
        "last_active_at": info.last_active_at,
    }


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    """流式聊天：SSE 返回 assistant_chunk / tool_call / plan / task_finish / error。"""
    info = await ensure_session(
        channel=body.channel,
        channel_user_id=body.channel_user_id,
        channel_session_id=body.channel_session_id or body.session_id or "",
        session_id=body.session_id,
    )

    async def event_stream():
        async for event in stream_reply(
            message=body.message,
            session_id=info.session_id,
        ):
            yield format_event_for_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

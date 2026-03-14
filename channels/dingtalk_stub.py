# -*- coding: utf-8 -*-
"""
钉钉渠道适配器占位示例。
扩展步骤：
1. 实现 parse_request：从钉钉回调 body 解析出 sender_id、conversation_id、消息文本。
2. 实现 send_stream：将 events 聚合成完整回复文本，调用钉钉机器人 API 回写。
3. 在 app 中注册路由：POST /channels/dingtalk 接收回调，调用本适配器 + chat_service.stream_reply。
"""
from __future__ import annotations

from channels.base import ChannelAdapter, InboundEvent
from core.session import SessionInfo
from typing import Any, AsyncIterator


class DingTalkChannelAdapter(ChannelAdapter):
    """钉钉渠道占位，实际接入时需实现 parse_request 与 send_stream。"""

    @property
    def channel_id(self) -> str:
        return "dingtalk"

    async def parse_request(self, raw: Any) -> InboundEvent | None:
        # 示例：raw 为钉钉 POST body，解析 msgtype、senderId、conversationId、text.content
        if not isinstance(raw, dict):
            return None
        msg = raw.get("text", {}) or raw.get("content", {})
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        sender = (raw.get("senderId") or raw.get("sender_id") or "unknown") if isinstance(raw, dict) else "unknown"
        conv = (raw.get("conversationId") or raw.get("conversation_id") or "") if isinstance(raw, dict) else ""
        if not content and not conv:
            return None
        return InboundEvent(
            channel=self.channel_id,
            channel_user_id=str(sender),
            channel_session_id=str(conv),
            message=content.strip() or "(空消息)",
            raw=raw,
        )

    async def send_stream(
        self,
        session_info: SessionInfo,
        events: AsyncIterator[dict],
    ) -> None:
        # 占位：实际应聚合 assistant_chunk 文本，再调钉钉 API 发送
        async for _ in events:
            pass

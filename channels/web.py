# -*- coding: utf-8 -*-
"""Web 渠道：由 REST/SSE API 与前端直接消费，无需单独适配器逻辑。"""
from __future__ import annotations

from channels.base import ChannelAdapter, InboundEvent


class WebChannelAdapter(ChannelAdapter):
    """
    Web 渠道使用 /api/chat 与 /api/sessions，由 app.routes.chat 直接处理。
    本适配器仅作注册与占位，实际入站由 FastAPI 请求体解析。
    """

    @property
    def channel_id(self) -> str:
        return "web"

    async def parse_request(self, raw: object) -> InboundEvent | None:
        # Web 请求已在路由中解析，此处不用于入站解析
        return None

    async def send_stream(self, session_info, events):
        # 流式响应由 StreamingResponse 在路由中直接写入
        async for _ in events:
            pass

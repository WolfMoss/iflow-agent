# -*- coding: utf-8 -*-
"""通道适配器抽象：入参标准化、出参按渠道格式化。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator

from core.session import SessionInfo


@dataclass
class InboundEvent:
    """渠道侧标准化入参。"""

    channel: str
    channel_user_id: str
    channel_session_id: str
    message: str
    raw: Any = None


class ChannelAdapter(ABC):
    """单渠道适配器：解析渠道请求、调用桥接、回写渠道。"""

    @property
    @abstractmethod
    def channel_id(self) -> str:
        """渠道唯一标识。"""
        pass

    @abstractmethod
    async def parse_request(self, raw: Any) -> InboundEvent | None:
        """将渠道原始请求解析为 InboundEvent，无法解析时返回 None。"""
        pass

    @abstractmethod
    async def send_stream(
        self,
        session_info: SessionInfo,
        events: AsyncIterator[dict],
    ) -> None:
        """将流式事件按渠道格式回写（如 HTTP 响应、钉钉 API、Telegram API）。"""
        pass


class AdapterRegistry:
    """渠道注册表，便于按 channel_id 获取适配器。"""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel_id] = adapter

    def get(self, channel_id: str) -> ChannelAdapter | None:
        return self._adapters.get(channel_id)

    def all_channels(self) -> list[str]:
        return list(self._adapters.keys())

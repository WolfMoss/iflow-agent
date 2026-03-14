# -*- coding: utf-8 -*-
"""会话存储抽象与内存实现，便于后续扩展 Redis。"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionInfo:
    """单条会话信息。"""

    session_id: str
    channel: str
    channel_user_id: str
    channel_session_id: str
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active_at = time.time()


class SessionStore(ABC):
    """会话存储抽象。"""

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionInfo]:
        pass

    @abstractmethod
    def set(self, info: SessionInfo) -> None:
        pass

    @abstractmethod
    def create(
        self,
        channel: str,
        channel_user_id: str,
        channel_session_id: str,
        session_id: Optional[str] = None,
    ) -> SessionInfo:
        pass

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        pass


class MemorySessionStore(SessionStore):
    """内存会话存储，单进程适用。"""

    def __init__(self) -> None:
        self._store: dict[str, SessionInfo] = {}

    def get(self, session_id: str) -> Optional[SessionInfo]:
        info = self._store.get(session_id)
        if info:
            info.touch()
        return info

    def set(self, info: SessionInfo) -> None:
        info.touch()
        self._store[info.session_id] = info

    def create(
        self,
        channel: str,
        channel_user_id: str,
        channel_session_id: str,
        session_id: Optional[str] = None,
    ) -> SessionInfo:
        sid = session_id or str(uuid.uuid4())
        info = SessionInfo(
            session_id=sid,
            channel=channel,
            channel_user_id=channel_user_id,
            channel_session_id=channel_session_id,
        )
        self._store[sid] = info
        return info

    def delete(self, session_id: str) -> bool:
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False


def get_session_store(redis_url: str = "") -> SessionStore:
    """根据配置返回会话存储实例。"""
    if redis_url:
        # 预留：RedisSessionStore(redis_url)
        pass
    return MemorySessionStore()

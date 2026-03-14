# -*- coding: utf-8 -*-
"""会话存储抽象与内存实现，便于后续扩展 Redis。"""
from __future__ import annotations

import json
import logging
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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


def _channel_key(channel: str, channel_user_id: str, channel_session_id: str) -> str:
    """渠道+用户+会话唯一键，用于「当前会话」覆盖（如 /new 后）。"""
    return f"{channel}:{channel_user_id}:{channel_session_id}"


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

    @abstractmethod
    def get_current_session_id(
        self, channel: str, channel_user_id: str, channel_session_id: str
    ) -> Optional[str]:
        """获取该渠道用户会话下由 /new 等设置的「当前会话」ID；无则返回 None。"""
        pass

    @abstractmethod
    def set_current_session_id(
        self,
        channel: str,
        channel_user_id: str,
        channel_session_id: str,
        session_id: str,
    ) -> None:
        """设置该渠道用户会话的当前会话 ID（如 /new 后）。"""
        pass


class MemorySessionStore(SessionStore):
    """内存会话存储；「当前会话」覆盖可持久化到文件，重启后仍生效。"""

    def __init__(self, current_sessions_path: str | Path | None = None) -> None:
        self._store: dict[str, SessionInfo] = {}
        self._current: dict[str, str] = {}
        self._current_path: Path | None = (
            Path(current_sessions_path) if current_sessions_path else None
        )
        self._load_current()

    def _load_current(self) -> None:
        if not self._current_path:
            return
        try:
            if self._current_path.is_file():
                text = self._current_path.read_text(encoding="utf-8")
                data = json.loads(text)
                if isinstance(data, dict):
                    self._current = {k: str(v) for k, v in data.items()}
        except Exception as e:
            logger.warning("加载当前会话覆盖文件失败，将使用空映射: %s", e)

    def _save_current(self) -> None:
        if not self._current_path:
            return
        try:
            self._current_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=self._current_path.parent,
                prefix=".current_sessions.",
                suffix=".json",
            )
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(self._current, f, ensure_ascii=False, indent=0)
            Path(tmp).replace(self._current_path)
        except Exception as e:
            logger.warning("保存当前会话覆盖文件失败: %s", e)

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

    def get_current_session_id(
        self, channel: str, channel_user_id: str, channel_session_id: str
    ) -> Optional[str]:
        key = _channel_key(channel, channel_user_id, channel_session_id)
        return self._current.get(key)

    def set_current_session_id(
        self,
        channel: str,
        channel_user_id: str,
        channel_session_id: str,
        session_id: str,
    ) -> None:
        key = _channel_key(channel, channel_user_id, channel_session_id)
        self._current[key] = session_id
        self._save_current()


def get_session_store(redis_url: str = "") -> SessionStore:
    """根据配置返回会话存储实例。当前会话覆盖会持久化到工作区下的 gateway_current_sessions.json。"""
    if redis_url:
        # 预留：RedisSessionStore(redis_url)，需实现 get_current_session_id / set_current_session_id
        pass
    from core.config import settings

    path = Path(settings.iflow_default_workspace_path()) / "gateway_current_sessions.json"
    return MemorySessionStore(current_sessions_path=path)

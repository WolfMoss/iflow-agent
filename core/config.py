# -*- coding: utf-8 -*-
"""应用配置，从环境变量加载。"""
from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    iflow_ws_url: str = "ws://localhost:8090/acp"
    # 启动网关时是否自动启动 iFlow 进程（手动模式，同 iflow --experimental-acp --port N）
    iflow_auto_start: bool = True
    # 默认工作区目录名，位于用户目录下；不设则用 .iflowagentworkspace
    iflow_workspace_dir_name: str = ".iflowagentworkspace"
    host: str = "0.0.0.0"
    port: int = 8000
    session_store_url: str = ""
    log_level: str = "INFO"
    iflow_timeout: float = 300.0

    # Telegram（可选，不配置则 Telegram 渠道不启用）
    telegram_bot_token: str = ""
    # 允许对话的 Telegram 用户 ID，逗号分隔；* 或 ALL 表示允许所有人；空表示不启用
    telegram_allow_from: str = ""
    # True 时仅使用 Webhook（需公网 HTTPS），不启动 Long Polling；默认 False，本地用 Long Polling 无需域名
    telegram_use_webhook: bool = False
    # 请求 Telegram API 的代理 URL（如 http://127.0.0.1:7890），空则不使用
    telegram_proxy: str = ""
    # 连接 Telegram API 的超时秒数（含 TLS），网络受限时可适当调大
    telegram_timeout: float = 60.0

    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.strip())

    def telegram_user_allowed(self, user_id: str) -> bool:
        if not self.telegram_allow_from:
            return False
        allow = self.telegram_allow_from.strip().upper()
        if allow in ("*", "ALL"):
            return True
        allowed_ids = [x.strip() for x in self.telegram_allow_from.split(",") if x.strip()]
        return user_id in allowed_ids

    def iflow_port(self) -> int:
        """从 iflow_ws_url 解析端口，用于自动启动 iFlow。"""
        try:
            p = urlparse(self.iflow_ws_url)
            if p.port is not None:
                return p.port
        except Exception:
            pass
        return 8090

    def iflow_default_workspace_path(self) -> str:
        """默认工作目录：用户目录下与 iflow_workspace_dir_name 同名的目录（绝对路径）。"""
        path = Path.home() / self.iflow_workspace_dir_name.strip() or ".iflowagentworkspace"
        return str(path.resolve())


settings = Settings()

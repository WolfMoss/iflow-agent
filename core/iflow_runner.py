# -*- coding: utf-8 -*-
"""启动网关时自动拉起 iFlow 进程（手动模式：iflow --experimental-acp --port N）。"""
import logging
import shutil
import subprocess
import sys

from core.config import settings

logger = logging.getLogger(__name__)


def start_iflow_process() -> subprocess.Popen | None:
    """
    若配置了 iflow_auto_start，则启动 iFlow 子进程并返回 Popen；
    否则返回 None。调用方需在应用退出时对返回值调用 terminate() / wait()。
    """
    if not settings.iflow_auto_start:
        return None

    if not shutil.which("iflow"):
        logger.warning(
            "未找到 iflow 可执行文件（请确保已安装 iFlow CLI 并加入 PATH），跳过自动启动"
        )
        return None

    port = settings.iflow_port()
    try:
        proc = _popen_iflow(port)
        if proc is not None:
            logger.info("已自动启动 iFlow 进程 (PID=%s, port=%s)，独立窗口可单独管理", proc.pid, port)
        return proc
    except Exception as e:
        logger.exception("启动 iFlow 进程失败: %s", e)
        return None


def _popen_iflow(port: int) -> subprocess.Popen | None:
    """启动 iflow 子进程。Windows 下用 shell 执行以避免 WinError 193（脚本/批处理非 Win32 可执行文件）。"""
    if sys.platform == "win32":
        cmd = f'iflow --experimental-acp --port {port}'
        return subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            creationflags=_subprocess_creation_flags(),
        )
    exe = shutil.which("iflow")
    return subprocess.Popen(
        [exe, "--experimental-acp", "--port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=None,
        stderr=None,
        creationflags=_subprocess_creation_flags(),
    )


def _subprocess_creation_flags() -> int:
    """Windows 下为 iFlow 创建独立控制台窗口，便于管理员查看与管理。"""
    if sys.platform == "win32":
        try:
            return subprocess.CREATE_NEW_CONSOLE
        except AttributeError:
            pass
    return 0

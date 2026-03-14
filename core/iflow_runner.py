# -*- coding: utf-8 -*-
"""启动网关时自动拉起 iFlow 进程（手动模式：iflow --experimental-acp --port N）。"""
import logging
import shutil
import subprocess
import sys

from core.config import settings

logger = logging.getLogger(__name__)


def kill_processes_on_port(port: int) -> None:
    """杀掉占用指定 TCP 端口的所有进程（Windows / Unix 通用）。

    shell=True + CREATE_NEW_CONSOLE 启动的 iflow 进程链为
    cmd.exe → iflow.cmd → node.exe。proc.terminate() 只杀 cmd.exe，
    node.exe 会变成孤儿进程继续占用端口。此函数按端口查杀，确保彻底清理。
    """
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                f'netstat -ano -p TCP | findstr ":{port} "',
                shell=True, text=True, stderr=subprocess.DEVNULL,
            )
            pids: set[int] = set()
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    try:
                        pids.add(int(parts[-1]))
                    except ValueError:
                        pass
            for pid in pids:
                logger.info("正在终止占用端口 %s 的进程 PID=%s", port, pid)
                subprocess.run(
                    f"taskkill /F /T /PID {pid}",
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except (subprocess.CalledProcessError, OSError):
            pass
    else:
        try:
            out = subprocess.check_output(
                ["lsof", "-ti", f":{port}"], text=True, stderr=subprocess.DEVNULL,
            )
            for pid_str in out.strip().splitlines():
                try:
                    pid = int(pid_str)
                    logger.info("正在终止占用端口 %s 的进程 PID=%s", port, pid)
                    import signal
                    import os as _os
                    _os.kill(pid, signal.SIGKILL)
                except (ValueError, OSError):
                    pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass


def stop_iflow_process(proc: subprocess.Popen | None) -> None:
    """终止 iFlow 进程树（包括 cmd.exe 和 node.exe 子进程）。"""
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            f"taskkill /F /T /PID {proc.pid}",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def start_iflow_process() -> subprocess.Popen | None:
    """
    若配置了 iflow_auto_start，则启动 iFlow 子进程并返回 Popen；
    否则返回 None。调用方需在应用退出时对返回值调用 stop_iflow_process()。
    """
    if not settings.iflow_auto_start:
        return None

    if not shutil.which("iflow"):
        logger.warning(
            "未找到 iflow 可执行文件（请确保已安装 iFlow CLI 并加入 PATH），跳过自动启动"
        )
        return None

    port = settings.iflow_port()
    workspace_dir = settings.iflow_default_workspace_path()

    kill_processes_on_port(port)

    try:
        proc = _popen_iflow(port, cwd=workspace_dir)
        if proc is not None:
            logger.info(
                "已自动启动 iFlow 进程 (PID=%s, port=%s, cwd=%s)",
                proc.pid, port, workspace_dir,
            )
        return proc
    except Exception as e:
        logger.exception("启动 iFlow 进程失败: %s", e)
        return None


def _popen_iflow(port: int, cwd: str | None = None) -> subprocess.Popen | None:
    if sys.platform == "win32":
        if cwd:
            cmd = f'cd /d "{cwd}" && iflow --experimental-acp --port {port}'
        else:
            cmd = f"iflow --experimental-acp --port {port}"
        return subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            cwd=cwd or None,
            creationflags=_subprocess_creation_flags(),
        )
    exe = shutil.which("iflow")
    return subprocess.Popen(
        [exe, "--experimental-acp", "--port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=None,
        stderr=None,
        cwd=cwd or None,
        creationflags=_subprocess_creation_flags(),
    )


def _subprocess_creation_flags() -> int:
    if sys.platform == "win32":
        try:
            return subprocess.CREATE_NEW_CONSOLE
        except AttributeError:
            pass
    return 0

# -*- coding: utf-8 -*-
"""
iFlow 管理 API（用于 Web UI）。

当前实现目标：
- Global 作用域（用户作用域）skills 列出与删除
- MCP 列出与删除（通过 iflow mcp list/remove 命令）
- 保存/删除后重启 iFlow ACP 进程（重新加载工具）
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.config import settings
from core.iflow_runner import restart_iflow_process, run_iflow_cli

router = APIRouter(prefix="/api/iflow", tags=["iflow-admin"])


class DeleteSkillsRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)


class DeleteMcpRequest(BaseModel):
    names: list[str] = Field(default_factory=list)


def _load_iflow_settings_json() -> dict[str, Any]:
    """读取 ~/.iflow/settings.json（容错：缺文件/解析失败返回空 dict）。"""
    settings_path = Path.home() / ".iflow" / "settings.json"
    if not settings_path.exists() or not settings_path.is_file():
        return {}
    try:
        text = settings_path.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def _save_iflow_settings_json(data: dict[str, Any]) -> None:
    """写回 ~/.iflow/settings.json。"""
    settings_path = Path.home() / ".iflow" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _global_skills_dir() -> Path:
    # iFlow 文档：global skills 通常在 ~/.iflow/skills
    return Path.home() / ".iflow" / "skills"


def _parse_skill_meta(skill_dir: Path) -> dict[str, str]:
    # 优先读取 SKILL.md 的 YAML frontmatter；否则退回目录名
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"id": skill_dir.name, "name": skill_dir.name, "description": ""}

    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"id": skill_dir.name, "name": skill_dir.name, "description": ""}

    # 前置 --- 到 --- 之间提 name/description
    m = re.search(r"^---\\s*\\n(.*?)\\n---\\s*$", text, flags=re.S | re.M)
    if not m:
        return {"id": skill_dir.name, "name": skill_dir.name, "description": ""}

    front = m.group(1)
    name_m = re.search(r"^name\\s*:\\s*(.+)$", front, flags=re.M)
    desc_m = re.search(r"^description\\s*:\\s*(.+)$", front, flags=re.M)
    name = (name_m.group(1).strip().strip('"').strip("'") if name_m else skill_dir.name)
    desc = (desc_m.group(1).strip().strip('"').strip("'") if desc_m else "")
    return {"id": skill_dir.name, "name": str(name), "description": str(desc)}


def _list_global_skills() -> list[dict[str, str]]:
    base = _global_skills_dir()
    if not base.exists():
        return []
    if not base.is_dir():
        return []

    skills: list[dict[str, str]] = []
    for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        skills.append(_parse_skill_meta(child))
    return skills


def _list_mcp_servers() -> list[dict[str, Any]]:
    """读取 iFlow 全局配置：~/.iflow/settings.json 中的 mcpServers。"""
    settings_path = Path.home() / ".iflow" / "settings.json"
    if not settings_path.exists() or not settings_path.is_file():
        return []

    try:
        text = settings_path.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(text)
    except Exception:
        return []

    mcp_servers = data.get("mcpServers") or data.get("mcp_servers") or {}
    if not isinstance(mcp_servers, dict):
        return []

    names = [str(k) for k in mcp_servers.keys()]
    names_sorted = sorted(names, key=lambda s: s.lower())
    return [{"name": n} for n in names_sorted]


@router.get("/skills")
async def list_skills() -> dict[str, Any]:
    """列出 global（用户作用域）的 skills。"""
    return {"scope": "global", "skills": _list_global_skills()}


@router.post("/skills/delete")
async def delete_skills(request: Request, body: DeleteSkillsRequest) -> dict[str, Any]:
    ids = body.ids or []
    if not ids:
        return {"ok": True, "deleted": 0, "skipped": []}

    base = _global_skills_dir()
    deleted = 0
    skipped: list[str] = []
    for skill_id in ids:
        target = base / skill_id
        if not target.exists():
            skipped.append(skill_id)
            continue
        try:
            shutil.rmtree(target)
            deleted += 1
        except Exception:
            skipped.append(skill_id)

    # 删除后重启 iFlow（重新加载 skills registry）
    app_proc = getattr(request.app.state, "iflow_process", None)
    new_proc = restart_iflow_process(app_proc)
    request.app.state.iflow_process = new_proc
    return {"ok": True, "deleted": deleted, "skipped": skipped}


@router.get("/mcp")
async def list_mcp() -> dict[str, Any]:
    """列出 MCP 服务器（来自 ~/.iflow/settings.json），并返回原始 iflow mcp list 输出用于判断是否生效。"""
    rc, out, err = run_iflow_cli(["mcp", "list"], timeout=15.0)
    mcp_list_output = (out or "").strip()
    if err:
        if mcp_list_output:
            mcp_list_output += "\n\n[stderr]\n" + err.strip()
        else:
            mcp_list_output = "[stderr]\n" + err.strip()

    return {
        "scope": "global",
        "servers": _list_mcp_servers(),
        "mcpListReturnCode": rc,
        "mcpListOutput": mcp_list_output,
    }


@router.post("/mcp/delete")
async def delete_mcp(request: Request, body: DeleteMcpRequest) -> dict[str, Any]:
    names = body.names or []
    if not names:
        return {"ok": True, "deleted": 0, "skipped": []}

    deleted = 0
    skipped: list[str] = []
    for name in names:
        # 为避免 iflow CLI 在 Windows 上的交互式等待导致 Web 请求卡住，
        # 这里直接按配置修改 ~/.iflow/settings.json 的 mcpServers。
        data = _load_iflow_settings_json()
        mcp_servers = data.get("mcpServers") or {}
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}
        if name in mcp_servers:
            mcp_servers.pop(name, None)
            data["mcpServers"] = mcp_servers
            _save_iflow_settings_json(data)
            deleted += 1
        else:
            skipped.append(name)

    app_proc = getattr(request.app.state, "iflow_process", None)
    new_proc = restart_iflow_process(app_proc)
    request.app.state.iflow_process = new_proc
    return {
        "ok": True,
        "deleted": deleted,
        "skipped": skipped,
        "restartedPid": getattr(new_proc, "pid", None),
    }


@router.post("/restart")
async def restart_admin(request: Request) -> dict[str, Any]:
    """手动重启 iFlow ACP（用于验证）。"""
    app_proc = getattr(request.app.state, "iflow_process", None)
    new_proc = restart_iflow_process(app_proc)
    request.app.state.iflow_process = new_proc
    return {"ok": True, "pid": getattr(new_proc, "pid", None)}


from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from pydantic import BaseModel


@dataclass
class RoleConfig:
    """轻量级配置对象，用于在 Coordinator 中声明角色。

    与 coordinator.py 中的使用保持兼容：
    RoleConfig(name="retriever", description="...", capabilities={"type": "retrieval"})
    """

    name: str
    description: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None


# --- Pydantic schemas for router input/output ---
class RoleConfigSchema(BaseModel):
    name: str
    description: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    model_id: Optional[str] = None
    prompt: Optional[str] = None
    roles: Optional[List[RoleConfigSchema]] = None


class SessionSummary(BaseModel):
    id: int
    user_id: int
    title: str
    model_id: Optional[str] = None
    status: str
    metadata: Optional[Dict[str, Any]] = None
    # aggregated result preview
    summary_title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SessionDetail(SessionSummary):
    tasks: Optional[List[Dict[str, Any]]] = None
    logs: Optional[List[Dict[str, Any]]] = None
    final_result: Optional[Dict[str, Any]] = None


class SessionStatusResponse(BaseModel):
    session: Dict[str, Any]
    recent_logs: List[Dict[str, Any]]
    active_tasks: List[Dict[str, Any]]


__all__ = [
    "RoleConfig",
    "RoleConfigSchema",
    "CreateSessionRequest",
    "SessionSummary",
    "SessionDetail",
    "SessionStatusResponse",
]

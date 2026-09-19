"""配置管理业务 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── 配置项 ──
class CICreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    ci_type: Literal["server", "network", "storage", "software"] = "server"
    environment: Literal["prod", "staging", "dev"] = "prod"
    owner: str = Field(default="", max_length=80)
    ip_address: str = Field(default="", max_length=64)


class CIUpdate(BaseModel):
    owner: str | None = Field(default=None, max_length=80)
    ip_address: str | None = Field(default=None, max_length=64)
    environment: Literal["prod", "staging", "dev"] | None = None


class CIStatusUpdate(BaseModel):
    status: Literal["in_service", "maintenance", "retired"]


# ── 配置项关系 ──
class CIRelationCreate(BaseModel):
    source_ci_id: str = Field(min_length=1, max_length=64)
    target_ci_id: str = Field(min_length=1, max_length=64)
    relation_type: Literal["depends_on", "connects_to", "hosts", "monitors"] = "depends_on"


class CIRelationStatusUpdate(BaseModel):
    status: Literal["active", "inactive"]


# ── 变更记录 ──
class ChangeCreate(BaseModel):
    ci_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    change_type: Literal["routine", "std", "emergency"] = "routine"
    requester: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=2000)


class ChangeStatusUpdate(BaseModel):
    status: Literal["planned", "approved", "implemented", "closed"]

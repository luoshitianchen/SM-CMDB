"""配置管理业务服务层：配置项/关系/变更全生命周期。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.cmdb import CI, ChangeRecord, CIRelation
from app.repositories import cmdb as repo
from app.schemas.cmdb import (
    ChangeCreate,
    ChangeStatusUpdate,
    CICreate,
    CIRelationCreate,
    CIRelationStatusUpdate,
    CIStatusUpdate,
    CIUpdate,
)
from app.services.audit import record_audit

# 变更记录状态机：planned -> approved -> implemented -> closed
_CHANGE_TRANSITIONS = {
    "planned": {"approved"},
    "approved": {"implemented"},
    "implemented": {"closed"},
    "closed": set(),
}


def _ci_to_dict(c: CI) -> dict:
    return {
        "id": c.id, "name": c.name, "ci_type": c.ci_type,
        "environment": c.environment, "status": c.status,
        "owner": c.owner, "ip_address": c.ip_address,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


def _relation_to_dict(r: CIRelation) -> dict:
    return {
        "id": r.id, "source_ci_id": r.source_ci_id, "target_ci_id": r.target_ci_id,
        "relation_type": r.relation_type, "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


def _change_to_dict(c: ChangeRecord) -> dict:
    return {
        "id": c.id, "ci_id": c.ci_id, "title": c.title,
        "change_type": c.change_type, "status": c.status,
        "requester": c.requester, "description": c.description,
        "completed_at": c.completed_at.isoformat() if c.completed_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


class CMDBService:
    """CMDB 领域服务。"""

    @staticmethod
    def _require_write(request: Request) -> None:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")

    # ── 配置项 ──
    @staticmethod
    async def list_cis(session: AsyncSession, limit: int = 100, offset: int = 0,
                       ci_type: str | None = None, environment: str | None = None,
                       status_filter: str | None = None, keyword: str | None = None) -> dict:
        items = await repo.list_cis(session, limit=limit, offset=offset, ci_type=ci_type,
                                    environment=environment, status=status_filter, keyword=keyword)
        total = await repo.count_cis(session, ci_type=ci_type, environment=environment,
                                    status=status_filter, keyword=keyword)
        return {"total": total, "items": [_ci_to_dict(c) for c in items]}

    @staticmethod
    async def get_ci(session: AsyncSession, ci_id: str) -> dict:
        ci = await repo.get_ci(session, ci_id)
        if not ci:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        return _ci_to_dict(ci)

    @staticmethod
    async def create_ci(session: AsyncSession, payload: CICreate, request: Request) -> dict:
        CMDBService._require_write(request)
        if await repo.get_ci_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "配置项名称已存在")
        ci = CI(
            id=str(uuid.uuid4()), name=payload.name, ci_type=payload.ci_type,
            environment=payload.environment, owner=payload.owner,
            ip_address=payload.ip_address, status="in_service",
        )
        ci = await repo.save_ci(session, ci)
        await record_audit(session, "cmdb.ci.created", "internal",
                           f"ci_id={ci.id} name={payload.name}", request)
        return _ci_to_dict(ci)

    @staticmethod
    async def update_ci(session: AsyncSession, ci_id: str,
                        payload: CIUpdate, request: Request) -> dict:
        CMDBService._require_write(request)
        ci = await repo.get_ci(session, ci_id)
        if not ci:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        if payload.owner is not None:
            ci.owner = payload.owner
        if payload.ip_address is not None:
            ci.ip_address = payload.ip_address
        if payload.environment is not None:
            ci.environment = payload.environment
        ci = await repo.save_ci(session, ci)
        await record_audit(session, "cmdb.ci.updated", "internal",
                           f"ci_id={ci_id}", request)
        return _ci_to_dict(ci)

    @staticmethod
    async def update_ci_status(session: AsyncSession, ci_id: str,
                               payload: CIStatusUpdate, request: Request) -> dict:
        CMDBService._require_write(request)
        ci = await repo.get_ci(session, ci_id)
        if not ci:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        ci.status = payload.status
        ci = await repo.save_ci(session, ci)
        await record_audit(session, "cmdb.ci.status_changed", "internal",
                           f"ci_id={ci_id} status={payload.status}", request)
        return _ci_to_dict(ci)

    # ── 配置项关系 ──
    @staticmethod
    async def list_relations(session: AsyncSession, limit: int = 100, offset: int = 0,
                             source_ci_id: str | None = None,
                             relation_type: str | None = None) -> dict:
        items = await repo.list_relations(session, limit=limit, offset=offset,
                                          source_ci_id=source_ci_id, relation_type=relation_type)
        total = await repo.count_relations(session, source_ci_id=source_ci_id,
                                           relation_type=relation_type)
        return {"total": total, "items": [_relation_to_dict(r) for r in items]}

    @staticmethod
    async def create_relation(session: AsyncSession, payload: CIRelationCreate,
                              request: Request) -> dict:
        CMDBService._require_write(request)
        if payload.source_ci_id == payload.target_ci_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "配置项不能与自身建立关系")
        if not await repo.get_ci(session, payload.source_ci_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "源配置项不存在")
        if not await repo.get_ci(session, payload.target_ci_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "目标配置项不存在")
        if await repo.find_relation(session, payload.source_ci_id, payload.target_ci_id,
                                    payload.relation_type):
            raise HTTPException(status.HTTP_409_CONFLICT, "该配置项关系已存在")
        rel = CIRelation(
            id=str(uuid.uuid4()), source_ci_id=payload.source_ci_id,
            target_ci_id=payload.target_ci_id, relation_type=payload.relation_type,
            status="active",
        )
        rel = await repo.save_relation(session, rel)
        await record_audit(session, "cmdb.relation.created", "internal",
                           f"rel_id={rel.id} type={payload.relation_type}", request)
        return _relation_to_dict(rel)

    @staticmethod
    async def update_relation_status(session: AsyncSession, rel_id: str,
                                      payload: CIRelationStatusUpdate, request: Request) -> dict:
        CMDBService._require_write(request)
        rel = await repo.get_relation(session, rel_id)
        if not rel:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项关系不存在")
        rel.status = payload.status
        rel = await repo.save_relation(session, rel)
        await record_audit(session, "cmdb.relation.status_changed", "internal",
                           f"rel_id={rel_id} status={payload.status}", request)
        return _relation_to_dict(rel)

    # ── 变更记录 ──
    @staticmethod
    async def list_changes(session: AsyncSession, limit: int = 100, offset: int = 0,
                           status_filter: str | None = None,
                           ci_id: str | None = None) -> dict:
        items = await repo.list_changes(session, limit=limit, offset=offset,
                                        status=status_filter, ci_id=ci_id)
        total = await repo.count_changes(session, status=status_filter, ci_id=ci_id)
        return {"total": total, "items": [_change_to_dict(c) for c in items]}

    @staticmethod
    async def get_change(session: AsyncSession, change_id: str) -> dict:
        change = await repo.get_change(session, change_id)
        if not change:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "变更记录不存在")
        return _change_to_dict(change)

    @staticmethod
    async def create_change(session: AsyncSession, payload: ChangeCreate,
                            request: Request) -> dict:
        CMDBService._require_write(request)
        if not await repo.get_ci(session, payload.ci_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "关联的配置项不存在")
        change = ChangeRecord(
            id=str(uuid.uuid4()), ci_id=payload.ci_id, title=payload.title,
            change_type=payload.change_type, requester=payload.requester,
            description=payload.description, status="planned",
        )
        change = await repo.save_change(session, change)
        await record_audit(session, "cmdb.change.created", "internal",
                           f"change_id={change.id} title={payload.title}", request)
        return _change_to_dict(change)

    @staticmethod
    async def update_change_status(session: AsyncSession, change_id: str,
                                   payload: ChangeStatusUpdate, request: Request) -> dict:
        CMDBService._require_write(request)
        change = await repo.get_change(session, change_id)
        if not change:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "变更记录不存在")
        new_status = payload.status
        if new_status == change.status:
            return _change_to_dict(change)
        if new_status not in _CHANGE_TRANSITIONS.get(change.status, set()):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"非法状态迁移: {change.status} -> {new_status}")
        change.status = new_status
        if new_status == "closed":
            change.completed_at = datetime.now(UTC)
        change = await repo.save_change(session, change)
        await record_audit(session, "cmdb.change.status_changed", "internal",
                           f"change_id={change_id} status={new_status}", request)
        return _change_to_dict(change)

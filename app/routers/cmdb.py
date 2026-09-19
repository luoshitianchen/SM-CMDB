"""配置管理业务路由：配置项 / 配置项关系 / 变更记录。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.cmdb import (
    ChangeCreate,
    ChangeStatusUpdate,
    CICreate,
    CIRelationCreate,
    CIRelationStatusUpdate,
    CIStatusUpdate,
    CIUpdate,
)
from app.services.cmdb import CMDBService

router = APIRouter(prefix="/api/cmdb", tags=["cmdb"])


# ── 配置项 ──
@router.get("/cis")
async def list_cis(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ci_type: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.list_cis(session, limit=limit, offset=offset, ci_type=ci_type,
                                     environment=environment, status_filter=status_filter,
                                     keyword=keyword)


@router.post("/cis", status_code=status.HTTP_201_CREATED)
async def create_ci(
    payload: CICreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.create_ci(session, payload, request)


@router.get("/cis/{ci_id}")
async def get_ci(
    ci_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.get_ci(session, ci_id)


@router.patch("/cis/{ci_id}")
async def update_ci(
    ci_id: str, payload: CIUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.update_ci(session, ci_id, payload, request)


@router.patch("/cis/{ci_id}/status")
async def update_ci_status(
    ci_id: str, payload: CIStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.update_ci_status(session, ci_id, payload, request)


# ── 配置项关系 ──
@router.get("/relations")
async def list_relations(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source_ci_id: str | None = Query(default=None),
    relation_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.list_relations(session, limit=limit, offset=offset,
                                            source_ci_id=source_ci_id,
                                            relation_type=relation_type)


@router.post("/relations", status_code=status.HTTP_201_CREATED)
async def create_relation(
    payload: CIRelationCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.create_relation(session, payload, request)


@router.patch("/relations/{rel_id}/status")
async def update_relation_status(
    rel_id: str, payload: CIRelationStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.update_relation_status(session, rel_id, payload, request)


# ── 变更记录 ──
@router.get("/changes")
async def list_changes(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    ci_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.list_changes(session, limit=limit, offset=offset,
                                          status_filter=status_filter, ci_id=ci_id)


@router.post("/changes", status_code=status.HTTP_201_CREATED)
async def create_change(
    payload: ChangeCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.create_change(session, payload, request)


@router.get("/changes/{change_id}")
async def get_change(
    change_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.get_change(session, change_id)


@router.patch("/changes/{change_id}/status")
async def update_change_status(
    change_id: str, payload: ChangeStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await CMDBService.update_change_status(session, change_id, payload, request)

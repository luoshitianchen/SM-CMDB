"""配置管理业务仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cmdb import CI, ChangeRecord, CIRelation


# ── 配置项 ──
async def get_ci(session: AsyncSession, ci_id: str) -> CI | None:
    result = await session.execute(select(CI).where(CI.id == ci_id))
    return result.scalar_one_or_none()


async def get_ci_by_name(session: AsyncSession, name: str) -> CI | None:
    result = await session.execute(select(CI).where(CI.name == name))
    return result.scalar_one_or_none()


async def list_cis(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    ci_type: str | None = None, environment: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> list[CI]:
    stmt = select(CI).order_by(CI.created_at.desc()).limit(limit).offset(offset)
    if ci_type:
        stmt = stmt.where(CI.ci_type == ci_type)
    if environment:
        stmt = stmt.where(CI.environment == environment)
    if status:
        stmt = stmt.where(CI.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(CI.name.like(like), CI.ip_address.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_cis(
    session: AsyncSession, ci_type: str | None = None,
    environment: str | None = None, status: str | None = None,
    keyword: str | None = None,
) -> int:
    stmt = select(func.count(CI.id))
    if ci_type:
        stmt = stmt.where(CI.ci_type == ci_type)
    if environment:
        stmt = stmt.where(CI.environment == environment)
    if status:
        stmt = stmt.where(CI.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(CI.name.like(like), CI.ip_address.like(like)))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_ci(session: AsyncSession, ci: CI) -> CI:
    session.add(ci)
    await session.commit()
    await session.refresh(ci)
    return ci


# ── 配置项关系 ──
async def get_relation(session: AsyncSession, rel_id: str) -> CIRelation | None:
    result = await session.execute(select(CIRelation).where(CIRelation.id == rel_id))
    return result.scalar_one_or_none()


async def find_relation(
    session: AsyncSession, source_ci_id: str, target_ci_id: str,
    relation_type: str,
) -> CIRelation | None:
    result = await session.execute(
        select(CIRelation).where(
            CIRelation.source_ci_id == source_ci_id,
            CIRelation.target_ci_id == target_ci_id,
            CIRelation.relation_type == relation_type,
        )
    )
    return result.scalar_one_or_none()


async def list_relations(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    source_ci_id: str | None = None, relation_type: str | None = None,
) -> list[CIRelation]:
    stmt = select(CIRelation).order_by(CIRelation.created_at.desc()).limit(limit).offset(offset)
    if source_ci_id:
        stmt = stmt.where(CIRelation.source_ci_id == source_ci_id)
    if relation_type:
        stmt = stmt.where(CIRelation.relation_type == relation_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_relations(
    session: AsyncSession, source_ci_id: str | None = None,
    relation_type: str | None = None,
) -> int:
    stmt = select(func.count(CIRelation.id))
    if source_ci_id:
        stmt = stmt.where(CIRelation.source_ci_id == source_ci_id)
    if relation_type:
        stmt = stmt.where(CIRelation.relation_type == relation_type)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_relation(session: AsyncSession, rel: CIRelation) -> CIRelation:
    session.add(rel)
    await session.commit()
    await session.refresh(rel)
    return rel


# ── 变更记录 ──
async def get_change(session: AsyncSession, change_id: str) -> ChangeRecord | None:
    result = await session.execute(select(ChangeRecord).where(ChangeRecord.id == change_id))
    return result.scalar_one_or_none()


async def list_changes(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, ci_id: str | None = None,
) -> list[ChangeRecord]:
    stmt = select(ChangeRecord).order_by(ChangeRecord.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(ChangeRecord.status == status)
    if ci_id:
        stmt = stmt.where(ChangeRecord.ci_id == ci_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_changes(
    session: AsyncSession, status: str | None = None,
    ci_id: str | None = None,
) -> int:
    stmt = select(func.count(ChangeRecord.id))
    if status:
        stmt = stmt.where(ChangeRecord.status == status)
    if ci_id:
        stmt = stmt.where(ChangeRecord.ci_id == ci_id)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_change(session: AsyncSession, change: ChangeRecord) -> ChangeRecord:
    session.add(change)
    await session.commit()
    await session.refresh(change)
    return change

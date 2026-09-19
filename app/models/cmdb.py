"""配置管理业务模型：配置项、配置项关系、变更记录。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class CI(Base):
    """配置项（Configuration Item）：CMDB 核心资产对象。"""

    __tablename__ = "cis"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    ci_type: Mapped[str] = mapped_column(String(16), default="server", index=True)
    environment: Mapped[str] = mapped_column(String(16), default="prod", index=True)
    status: Mapped[str] = mapped_column(String(16), default="in_service", index=True)
    owner: Mapped[str] = mapped_column(String(80), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CIRelation(Base):
    """配置项关系：描述两个配置项之间的依赖/连接/承载关系。"""

    __tablename__ = "ci_relations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_ci_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_ci_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(16), default="depends_on", index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChangeRecord(Base):
    """变更记录：配置项变更的申请与执行轨迹。"""

    __tablename__ = "change_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ci_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    change_type: Mapped[str] = mapped_column(String(16), default="routine")
    status: Mapped[str] = mapped_column(String(16), default="planned", index=True)
    requester: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

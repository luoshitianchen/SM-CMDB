"""SM CMDB —— 配置管理数据库：配置项、类型、关联关系与变更历史。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-cmdb"
VERSION = "2.0.0"
NAME = "SM CMDB"
DESCRIPTION = "配置管理数据库：配置项、类型、关联关系与变更历史"
PORT = 8380


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS item_types (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL UNIQUE,
                identifier TEXT NOT NULL, environment TEXT NOT NULL DEFAULT 'prod',
                owner TEXT NOT NULL, attributes TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
                relation TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS changes (
                id TEXT PRIMARY KEY, item_id TEXT NOT NULL, field TEXT NOT NULL,
                old_value TEXT, new_value TEXT, changed_by TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_items_type ON items(type, environment);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-observability", "sm-audit-log-center"],
    events=["ci.created", "ci.updated", "ci.relationship_added"],
    overview_fn=lambda _r: {
        "summary": {
            "items": base.get_db().execute("SELECT COUNT(*) FROM items").fetchone()[0],
            "types": base.get_db().execute("SELECT COUNT(*) FROM item_types").fetchone()[0],
        }
    },
)
_init()


class TypeIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)


class ItemIn(BaseModel):
    type: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=80)
    identifier: str = Field(min_length=2, max_length=80)
    environment: str = Field(default="prod", pattern=r"^(prod|staging|dev|test)$")
    owner: str = Field(default="平台工程部", min_length=1, max_length=80)
    attributes: dict[str, Any] = Field(default_factory=dict)


class UpdateIn(BaseModel):
    attributes: dict[str, Any] = Field(min_length=1)
    changed_by: str = Field(min_length=1, max_length=80)


class RelationIn(BaseModel):
    source_id: str = Field(min_length=8)
    target_id: str = Field(min_length=8)
    relation: str = Field(min_length=2, max_length=60)


@app.get("/api/cmdb/types")
def list_types() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM item_types ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/cmdb/types", status_code=status.HTTP_201_CREATED)
def create_type(payload: TypeIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    type_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO item_types VALUES (?,?,?)", (type_id, payload.name, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "配置项类型已存在") from exc
    return {"id": type_id, "name": payload.name}


@app.post("/api/cmdb/items", status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    item_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM item_types WHERE name=?", (payload.type,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项类型不存在")
        try:
            conn.execute("INSERT INTO items (id, type, name, identifier, environment, owner, attributes, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (item_id, payload.type, payload.name, payload.identifier, payload.environment, payload.owner, json.dumps(payload.attributes, ensure_ascii=False), "active", _now(), _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "配置项已存在") from exc
        base.record_audit("ci.created", "internal", f"item={item_id} type={payload.type}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": item_id, "name": payload.name}


@app.get("/api/cmdb/items")
def list_items(type_: str | None = None, environment: str | None = None) -> dict[str, Any]:
    clauses, params = [], []
    if type_:
        clauses.append("type=?")
        params.append(type_)
    if environment:
        clauses.append("environment=?")
        params.append(environment)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with base.db_ctx() as conn:
        rows = conn.execute(f"SELECT * FROM items{where} ORDER BY updated_at DESC LIMIT 200", params).fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/cmdb/items/{item_id}")
def get_item(item_id: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
    return dict(row)


@app.put("/api/cmdb/items/{item_id}")
def update_item(item_id: str, payload: UpdateIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        old_attrs = json.loads(row["attributes"])
        new_attrs = json.dumps(payload.attributes, ensure_ascii=False)
        # 记录字段级变更
        for field, new_value in payload.attributes.items():
            old_value = old_attrs.get(field)
            if old_value != new_value:
                conn.execute("INSERT INTO changes (id, item_id, field, old_value, new_value, changed_by, created_at) VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), item_id, field, json.dumps(old_value, ensure_ascii=False) if old_value is not None else None, json.dumps(new_value, ensure_ascii=False), payload.changed_by, _now()))
        conn.execute("UPDATE items SET attributes=?, updated_at=? WHERE id=?", (new_attrs, _now(), item_id))
        base.record_audit("ci.updated", payload.changed_by, f"item={item_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": item_id, "updated": True}


@app.post("/api/cmdb/relationships", status_code=status.HTTP_201_CREATED)
def add_relationship(payload: RelationIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    relation_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM items WHERE id=?", (payload.source_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "源配置项不存在")
        if not conn.execute("SELECT 1 FROM items WHERE id=?", (payload.target_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标配置项不存在")
        conn.execute("INSERT INTO relationships VALUES (?,?,?,?,?)", (relation_id, payload.source_id, payload.target_id, payload.relation, _now()))
    return {"id": relation_id, "source_id": payload.source_id, "relation": payload.relation}


@app.get("/api/cmdb/items/{item_id}/relationships")
def get_relationships(item_id: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        outgoing = conn.execute("SELECT * FROM relationships WHERE source_id=?", (item_id,)).fetchall()
        incoming = conn.execute("SELECT * FROM relationships WHERE target_id=?", (item_id,)).fetchall()
    return {"item_id": item_id, "outgoing": [dict(r) for r in outgoing], "incoming": [dict(r) for r in incoming]}


@app.get("/api/cmdb/changes")
def list_changes(item_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(500, limit))
    with base.db_ctx() as conn:
        if item_id:
            rows = conn.execute("SELECT * FROM changes WHERE item_id=? ORDER BY created_at DESC LIMIT ?", (item_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM changes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/cmdb/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        by_type = [dict(r) for r in conn.execute("SELECT type, COUNT(*) AS count FROM items GROUP BY type").fetchall()]
        return {
            "types": _count("SELECT COUNT(*) FROM item_types"),
            "items": _count("SELECT COUNT(*) FROM items"),
            "relationships": _count("SELECT COUNT(*) FROM relationships"),
            "changes": _count("SELECT COUNT(*) FROM changes"),
            "by_type": by_type,
        }

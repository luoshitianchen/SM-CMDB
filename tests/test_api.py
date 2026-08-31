"""SM CMDB 领域测试：类型、配置项、属性变更历史、关联关系。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _type(client, name="server"):
    return client.post("/api/cmdb/types", json={"name": name}).json()["id"]


def _item(client, name="web-01", type_="server"):
    client.post("/api/cmdb/types", json={"name": type_})
    return client.post("/api/cmdb/items", json={"type": type_, "name": name, "identifier": f"host-{name}", "environment": "prod", "owner": "SRE", "attributes": {"ip": "10.0.0.1"}}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_type_and_item_crud(client):
    _type(client)
    _item(client)
    assert client.post("/api/cmdb/types", json={"name": "server"}).status_code == 409
    assert client.post("/api/cmdb/items", json={"type": "server", "name": "web-01", "identifier": "h2"}).status_code == 409
    assert client.get("/api/cmdb/types").json()["total"] == 1
    assert client.get("/api/cmdb/items").json()["total"] == 1


def test_item_requires_type(client):
    assert client.post("/api/cmdb/items", json={"type": "ghost", "name": "xx", "identifier": "hh"}).status_code == 404


def test_update_records_change(client):
    item_id = _item(client)
    assert client.put(f"/api/cmdb/items/{item_id}", json={"attributes": {"ip": "10.0.0.2"}, "changed_by": "运维小李"}).json()["updated"] is True
    changes = client.get("/api/cmdb/changes", params={"item_id": item_id}).json()
    assert changes["total"] >= 1
    assert changes["items"][0]["new_value"] == '"10.0.0.2"'


def test_relationship(client):
    a = _item(client, name="app-01")
    b = _item(client, name="db-01")
    rel = client.post("/api/cmdb/relationships", json={"source_id": a, "target_id": b, "relation": "depends_on"})
    assert rel.status_code == 201
    rels = client.get(f"/api/cmdb/items/{a}/relationships").json()
    assert len(rels["outgoing"]) == 1
    assert client.post("/api/cmdb/relationships", json={"source_id": a, "target_id": "no-such-item", "relation": "xx"}).status_code == 404


def test_stats(client):
    _type(client)
    _item(client)
    stats = client.get("/api/cmdb/stats").json()
    assert stats["types"] == 1
    assert stats["items"] == 1
    assert stats["by_type"][0]["count"] == 1


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/cmdb/types", json={"name": "t"}).status_code == 401

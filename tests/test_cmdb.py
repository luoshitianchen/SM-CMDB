"""配置管理业务深化测试：配置项/关系/变更记录。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


async def _make_ci(client, name: str = "ci-base-01", ci_type: str = "server") -> str:
    resp = await client.post("/api/cmdb/cis", json={
        "name": name, "ci_type": ci_type, "environment": "prod",
        "owner": "运维部", "ip_address": "10.0.0.1",
    }, headers=H)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ═══════════════════════════════════════════════════════════
# 配置项
# ═══════════════════════════════════════════════════════════
class TestCI:
    async def test_create_ci_success(self, client):
        resp = await client.post("/api/cmdb/cis", json={
            "name": "ci-biz-01", "ci_type": "server", "environment": "prod",
            "owner": "基础架构组", "ip_address": "10.1.1.1",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "ci-biz-01"
        assert data["status"] == "in_service"

    async def test_create_ci_requires_token(self, client):
        resp = await client.post("/api/cmdb/cis", json={
            "name": "ci-no-token", "ci_type": "server",
        })
        assert resp.status_code in (401, 403)

    async def test_create_ci_duplicate(self, client):
        await _make_ci(client, "ci-dup-01")
        resp = await client.post("/api/cmdb/cis", json={
            "name": "ci-dup-01", "ci_type": "server",
        }, headers=H)
        assert resp.status_code == 409

    async def test_list_cis(self, client):
        await _make_ci(client, "ci-list-01")
        resp = await client.get("/api/cmdb/cis", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_list_cis_type_filter(self, client):
        await _make_ci(client, "ci-net-01", ci_type="network")
        resp = await client.get("/api/cmdb/cis?ci_type=network", headers=H)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["ci_type"] == "network"

    async def test_list_cis_keyword(self, client):
        await client.post("/api/cmdb/cis", json={
            "name": "ci-kw-alpha", "ci_type": "server", "ip_address": "172.16.99.99",
        }, headers=H)
        resp = await client.get("/api/cmdb/cis?keyword=172.16.99", headers=H)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert "ci-kw-alpha" in names

    async def test_get_ci(self, client):
        ci_id = await _make_ci(client, "ci-get-01")
        resp = await client.get(f"/api/cmdb/cis/{ci_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == ci_id

    async def test_get_ci_not_found(self, client):
        resp = await client.get("/api/cmdb/cis/no-such", headers=H)
        assert resp.status_code == 404

    async def test_update_ci(self, client):
        ci_id = await _make_ci(client, "ci-upd-01")
        resp = await client.patch(f"/api/cmdb/cis/{ci_id}", json={
            "owner": "新负责人", "ip_address": "10.9.9.9",
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["owner"] == "新负责人"

    async def test_update_ci_status(self, client):
        ci_id = await _make_ci(client, "ci-stat-01")
        resp = await client.patch(f"/api/cmdb/cis/{ci_id}/status",
                                  json={"status": "maintenance"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "maintenance"


# ═══════════════════════════════════════════════════════════
# 配置项关系
# ═══════════════════════════════════════════════════════════
class TestCIRelation:
    async def test_create_relation_success(self, client):
        s = await _make_ci(client, "rel-src-01")
        t = await _make_ci(client, "rel-tgt-01")
        resp = await client.post("/api/cmdb/relations", json={
            "source_ci_id": s, "target_ci_id": t, "relation_type": "depends_on",
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["relation_type"] == "depends_on"

    async def test_relation_self_rejected(self, client):
        s = await _make_ci(client, "rel-self-01")
        resp = await client.post("/api/cmdb/relations", json={
            "source_ci_id": s, "target_ci_id": s, "relation_type": "depends_on",
        }, headers=H)
        assert resp.status_code == 400

    async def test_relation_missing_ci(self, client):
        s = await _make_ci(client, "rel-miss-01")
        resp = await client.post("/api/cmdb/relations", json={
            "source_ci_id": s, "target_ci_id": "no-such-ci", "relation_type": "hosts",
        }, headers=H)
        assert resp.status_code == 400

    async def test_relation_duplicate(self, client):
        s = await _make_ci(client, "rel-dup-s-01")
        t = await _make_ci(client, "rel-dup-t-01")
        await client.post("/api/cmdb/relations", json={
            "source_ci_id": s, "target_ci_id": t, "relation_type": "connects_to",
        }, headers=H)
        resp = await client.post("/api/cmdb/relations", json={
            "source_ci_id": s, "target_ci_id": t, "relation_type": "connects_to",
        }, headers=H)
        assert resp.status_code == 409

    async def test_list_relations_filter(self, client):
        s = await _make_ci(client, "rel-list-s-01")
        t = await _make_ci(client, "rel-list-t-01")
        await client.post("/api/cmdb/relations", json={
            "source_ci_id": s, "target_ci_id": t, "relation_type": "monitors",
        }, headers=H)
        resp = await client.get(f"/api/cmdb/relations?source_ci_id={s}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_relation_disable(self, client):
        s = await _make_ci(client, "rel-dis-s-01")
        t = await _make_ci(client, "rel-dis-t-01")
        created = await client.post("/api/cmdb/relations", json={
            "source_ci_id": s, "target_ci_id": t, "relation_type": "depends_on",
        }, headers=H)
        rel_id = created.json()["id"]
        resp = await client.patch(f"/api/cmdb/relations/{rel_id}/status",
                                  json={"status": "inactive"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"


# ═══════════════════════════════════════════════════════════
# 变更记录
# ═══════════════════════════════════════════════════════════
class TestChangeRecord:
    async def test_create_change_success(self, client):
        ci_id = await _make_ci(client, "chg-ci-01")
        resp = await client.post("/api/cmdb/changes", json={
            "ci_id": ci_id, "title": "升级内核", "change_type": "std",
            "requester": "张三", "description": "内核版本升级",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "planned"
        assert data["title"] == "升级内核"

    async def test_create_change_missing_ci(self, client):
        resp = await client.post("/api/cmdb/changes", json={
            "ci_id": "no-such-ci", "title": "幽灵变更",
        }, headers=H)
        assert resp.status_code == 400

    async def test_change_full_flow(self, client):
        ci_id = await _make_ci(client, "chg-flow-01")
        created = await client.post("/api/cmdb/changes", json={
            "ci_id": ci_id, "title": "全流程变更", "change_type": "routine",
        }, headers=H)
        cid = created.json()["id"]
        for st in ("approved", "implemented", "closed"):
            r = await client.patch(f"/api/cmdb/changes/{cid}/status",
                                   json={"status": st}, headers=H)
            assert r.status_code == 200, r.text
        assert r.json()["status"] == "closed"
        assert r.json()["completed_at"] is not None

    async def test_change_invalid_transition(self, client):
        ci_id = await _make_ci(client, "chg-bad-01")
        created = await client.post("/api/cmdb/changes", json={
            "ci_id": ci_id, "title": "越权变更",
        }, headers=H)
        cid = created.json()["id"]
        # planned 不能直接 -> implemented
        resp = await client.patch(f"/api/cmdb/changes/{cid}/status",
                                  json={"status": "implemented"}, headers=H)
        assert resp.status_code == 400

    async def test_list_changes_filter(self, client):
        ci_id = await _make_ci(client, "chg-list-01")
        await client.post("/api/cmdb/changes", json={
            "ci_id": ci_id, "title": "筛选变更",
        }, headers=H)
        resp = await client.get(f"/api/cmdb/changes?ci_id={ci_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_change_not_found(self, client):
        resp = await client.get("/api/cmdb/changes/no-such", headers=H)
        assert resp.status_code == 404

    async def test_change_requires_token(self, client):
        resp = await client.post("/api/cmdb/changes", json={
            "ci_id": "x", "title": "无令牌变更",
        })
        assert resp.status_code in (401, 403)

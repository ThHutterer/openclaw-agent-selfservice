import pytest


def test_create_agent(client):
    resp = client.post("/api/agents", json={
        "agent_id": "test-agent-1",
        "display_name": "Test Agent 1",
        "owner_name": "Tester",
        "organization": "test.org",
        "description": "A test agent",
        "model_primary": "google/gemini-2.5-flash-lite",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_id"] == "test-agent-1"
    assert data["status"] == "active"
    assert "id" in data
    assert "telegram_token_set" in data
    assert "workspace" in data
    assert "created_at" in data


def test_create_agent_invalid_slug_spaces(client):
    resp = client.post("/api/agents", json={
        "agent_id": "Test Agent",
        "display_name": "Bad Slug",
        "owner_name": "Tester",
        "organization": "test.org",
        "description": "Bad",
        "model_primary": "google/gemini-2.5-flash-lite",
    })
    assert resp.status_code == 400
    assert "agent_id" in resp.json()["detail"]


def test_create_agent_invalid_slug_uppercase(client):
    resp = client.post("/api/agents", json={
        "agent_id": "TestAgent",
        "display_name": "Bad Slug",
        "owner_name": "Tester",
        "organization": "test.org",
        "description": "Bad",
        "model_primary": "google/gemini-2.5-flash-lite",
    })
    assert resp.status_code == 400


def test_create_agent_duplicate(client):
    client.post("/api/agents", json={
        "agent_id": "dup-agent",
        "display_name": "Dup Agent",
        "owner_name": "Tester",
        "organization": "test.org",
        "description": "Dup",
        "model_primary": "google/gemini-2.5-flash-lite",
    })
    resp = client.post("/api/agents", json={
        "agent_id": "dup-agent",
        "display_name": "Dup Agent 2",
        "owner_name": "Tester",
        "organization": "test.org",
        "description": "Dup2",
        "model_primary": "google/gemini-2.5-flash-lite",
    })
    assert resp.status_code == 409


def test_list_agents(client):
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    agent_ids = [a["agent_id"] for a in data]
    assert "test-agent-1" in agent_ids


def test_get_agent(client):
    agents = client.get("/api/agents").json()
    agent = next(a for a in agents if a["agent_id"] == "test-agent-1")
    resp = client.get(f"/api/agents/{agent['id']}")
    assert resp.status_code == 200
    assert resp.json()["agent_id"] == "test-agent-1"


def test_get_agent_not_found(client):
    resp = client.get("/api/agents/nonexistent-uuid-12345")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Agent not found"


def test_delete_agent(client):
    create_resp = client.post("/api/agents", json={
        "agent_id": "delete-me",
        "display_name": "Delete Me",
        "owner_name": "Tester",
        "organization": "test.org",
        "description": "Will be deleted",
        "model_primary": "google/gemini-2.5-flash-lite",
    })
    assert create_resp.status_code == 201
    agent_db_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/agents/{agent_db_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True
    assert del_resp.json()["agent_id"] == "delete-me"


def test_delete_agent_not_found(client):
    resp = client.delete("/api/agents/nonexistent-uuid-99999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Agent not found"


def test_openclaw_status(client):
    resp = client.get("/api/openclaw/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "alive" in data
    assert "pid" in data
    assert "gateway_url" in data
    assert isinstance(data["alive"], bool)


def test_openclaw_reload(client):
    resp = client.post("/api/openclaw/reload")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.json()["ok"] is True


def test_smoke_create_verify_delete(client, tmp_openclaw_config):
    """Full roundtrip: create → verify in JSON → delete → verify removed"""
    import json as json_mod

    resp = client.post("/api/agents", json={
        "agent_id": "smoke-test",
        "display_name": "Smoke Test Agent",
        "owner_name": "QA Bot",
        "organization": "test.io",
        "description": "Smoke test agent",
        "model_primary": "google/gemini-2.5-flash-lite",
    })
    assert resp.status_code == 201
    agent_db_id = resp.json()["id"]

    config = json_mod.loads(tmp_openclaw_config.read_text())
    assert any(a["id"] == "smoke-test" for a in config["agents"]["list"])
    assert "smoke-test" in config["channels"]["telegram"]["accounts"]
    assert any(b["agentId"] == "smoke-test" for b in config["bindings"])

    del_resp = client.delete(f"/api/agents/{agent_db_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True

    config = json_mod.loads(tmp_openclaw_config.read_text())
    assert not any(a["id"] == "smoke-test" for a in config["agents"]["list"])
    assert "smoke-test" not in config["channels"]["telegram"]["accounts"]

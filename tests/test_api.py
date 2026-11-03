from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from supportforge.agent import AgentError
from supportforge.app import create_app
from supportforge.config import Settings

REQUEST = {"customer_name": "Demo Customer", "message": "I was charged twice for my subscription"}


def test_console_health_and_metadata(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "SupportForge" in response.text
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Request-ID"]
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/api/meta").json()["mode"] == "demo"
    assert len(client.get("/api/knowledge").json()) == 5
    assert client.get("/openapi.json").status_code == 200
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "https://cdn.jsdelivr.net" in docs.headers["Content-Security-Policy"]


def test_full_http_lifecycle(client):
    response = client.post("/api/runs", json=REQUEST, headers={"Idempotency-Key": "demo-1"})
    assert response.status_code == 201
    run = response.json()
    assert client.get(f"/api/runs/{run['id']}").json() == run
    assert len(client.get("/api/runs").json()) == 1
    assert (
        client.post("/api/runs", json=REQUEST, headers={"Idempotency-Key": "demo-1"}).json()["id"]
        == run["id"]
    )
    reviewed = client.post(
        f"/api/runs/{run['id']}/review", json={"decision": "approve", "reviewer": "Demo Operator"}
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["ticket_id"].startswith("SF-")
    assert client.get("/api/meta").json()["stats"]["tickets"] == 1
    assert len(client.get(f"/api/runs/{run['id']}/audit").json()) == 2
    assert (
        client.post(
            f"/api/runs/{run['id']}/review",
            json={"decision": "reject", "reviewer": "Demo Operator"},
        ).status_code
        == 409
    )


def test_bad_input_and_missing_runs(client):
    assert client.post("/api/runs", json={"message": "    "}).status_code == 422
    assert client.post("/api/runs", json={"message": "x" * 6001}).status_code == 422
    assert client.post("/api/runs", json={**REQUEST, "auto_approve": True}).status_code == 422
    assert client.post("/api/runs", json={**REQUEST, "customer_name": " "}).status_code == 422
    assert client.get("/api/runs?limit=999").status_code == 422
    assert client.get("/api/runs/missing").status_code == 404
    assert client.get("/api/runs/missing/audit").status_code == 404
    assert (
        client.post(
            "/api/runs/missing/review", json={"decision": "approve", "reviewer": "Tester"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/runs/missing/review", json={"decision": "approve", "reviewer": " "}
        ).status_code
        == 422
    )


def test_idempotency_conflict_exposed_as_409(client):
    client.post("/api/runs", json=REQUEST, headers={"Idempotency-Key": "same"})
    result = client.post(
        "/api/runs",
        json={"message": "Please reset my password"},
        headers={"Idempotency-Key": "same"},
    )
    assert result.status_code == 409


def test_optional_token_protects_all_api_routes(settings):
    with TestClient(create_app(replace(settings, api_token="unit-test-token"))) as client:
        for url in ("/api/meta", "/api/knowledge", "/api/runs", "/api/runs/missing/audit"):
            assert client.get(url).status_code == 401
        assert client.post("/api/runs", json=REQUEST).status_code == 401
        assert client.get("/healthz").status_code == 200
        assert (
            client.get("/api/meta", headers={"Authorization": "Bearer wrong-token"}).status_code
            == 401
        )
        result = client.get("/api/meta", headers={"Authorization": "Bearer unit-test-token"})
        assert result.status_code == 200
        assert "unit-test-token" not in result.text


def test_agent_failure_becomes_safe_502(client, monkeypatch):
    async def failed(*args, **kwargs):
        raise AgentError("Model draft failed; check server configuration and try again")

    monkeypatch.setattr(client.app.state.agent, "draft", failed)
    assert client.post("/api/runs", json=REQUEST).status_code == 502


def test_database_survives_application_restart(settings):
    with TestClient(create_app(settings)) as first:
        run_id = first.post("/api/runs", json=REQUEST).json()["id"]
    with TestClient(create_app(settings)) as second:
        assert second.get(f"/api/runs/{run_id}").status_code == 200
        assert second.get("/api/meta").json()["stats"]["runs"] == 1


def test_environment_validation_and_secret_repr(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPPORTFORGE_DATABASE", str(tmp_path / "config.sqlite3"))
    monkeypatch.setenv("SUPPORTFORGE_MODE", "demo")
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-print")
    settings = Settings.from_env()
    assert settings.database == tmp_path / "config.sqlite3"
    assert "do-not-print" not in repr(settings)
    with pytest.raises(ValueError, match="must be demo or openai"):
        Settings(mode="unknown")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(mode="openai")
    with pytest.raises(ValueError, match="positive"):
        Settings(model_timeout=0)

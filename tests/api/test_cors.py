from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


def _cors_options(client: TestClient, origin: str):
    return client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_cors_allows_listed_origins(monkeypatch):
    monkeypatch.setenv(
        "TFM_ALLOWED_ORIGINS",
        "https://dash.example.com, https://ops.example.com",
    )
    app = create_app()
    with TestClient(app) as client:
        response = _cors_options(client, "https://ops.example.com")
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://ops.example.com"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejects_unlisted_origin(monkeypatch):
    monkeypatch.setenv("TFM_ALLOWED_ORIGINS", "https://dash.example.com")
    app = create_app()
    with TestClient(app) as client:
        response = _cors_options(client, "https://evil.example.com")
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None

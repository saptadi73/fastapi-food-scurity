from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import BaseModel

from main import create_app


def test_health_and_documentation():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["data"]["status"] == "ok"
        assert str(UUID(body["meta"]["request_id"])) == response.headers["X-Request-ID"]
        assert body["meta"]["execution_time_ms"] >= 0
        assert client.get("/docs").status_code == 200
        assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]


def test_missing_route_uses_envelope():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/missing")
        assert response.status_code == 404
        assert response.json()["success"] is False
        assert response.json()["code"] == 404


class Payload(BaseModel):
    count: int


def test_validation_uses_documented_400_without_echoing_input():
    app = create_app()

    @app.post("/test-validation")
    async def validate(payload: Payload):
        return payload

    with TestClient(app) as client:
        response = client.post("/test-validation", json={"count": "secret-input"})
        assert response.status_code == 400
        assert response.json()["errors"][0]["field"] == "body.count"
        assert "secret-input" not in response.text


def test_unexpected_error_does_not_expose_details():
    app = create_app()

    @app.get("/test-error")
    async def fail():
        raise RuntimeError("private connection details")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-error")
        assert response.status_code == 500
        assert response.json()["success"] is False
        assert "private connection details" not in response.text
        assert "X-Request-ID" in response.headers

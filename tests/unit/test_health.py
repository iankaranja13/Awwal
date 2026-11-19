"""Health endpoint behaviour."""

from fastapi.testclient import TestClient

from app import __version__


def test_health_returns_ok_at_root_path(client: TestClient) -> None:
    """Serve liveness details at the unprefixed alias."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["environment"] == "test"
    assert response.headers["x-request-id"]


def test_health_returns_ok_at_versioned_path(client: TestClient) -> None:
    """Serve liveness details at the versioned API path."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


def test_request_id_header_is_echoed_when_provided(client: TestClient) -> None:
    """Echo a caller-provided request id back in the response."""
    response = client.get("/health", headers={"X-Request-ID": "demo-request-1"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "demo-request-1"


def test_unknown_route_returns_not_found_error_body(client: TestClient) -> None:
    """Render unknown routes with the stable error body."""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Resource not found.", "details": {}}
    }

"""API error-body mapping behaviour."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import ForbiddenError, register_error_handlers


def _error_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/forbidden")
    def forbidden() -> None:
        raise ForbiddenError("No entry.")

    @app.get("/typed")
    def typed(n: int) -> dict[str, int]:
        return {"n": n}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom-secret-marker")

    return app


def test_awwal_error_maps_to_error_body() -> None:
    """Render application errors with the stable body shape."""
    response = TestClient(_error_app()).get("/forbidden")
    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "FORBIDDEN", "message": "No entry.", "details": {}}
    }


def test_method_not_allowed_maps_to_error_body() -> None:
    """Render 405s with the stable body shape."""
    response = TestClient(_error_app()).post("/forbidden")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_validation_error_omits_input_values() -> None:
    """Strip raw inputs from validation error details."""
    response = TestClient(_error_app()).get("/typed", params={"n": "not-an-int"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"]
    for item in body["error"]["details"]["errors"]:
        assert set(item) == {"loc", "msg", "type"}


def test_unexpected_error_hides_details() -> None:
    """Hide unexpected failure details from clients."""
    client = TestClient(_error_app(), raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "boom-secret-marker" not in response.text

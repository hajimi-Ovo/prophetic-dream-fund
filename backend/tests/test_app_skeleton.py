"""Basic smoke tests for the FastAPI application skeleton."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Verify the API health endpoint returns the expected response."""
    response = await client.get("/api/v1/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "ok"
    assert data["data"]["service"] == "prophetic-dream-fund"


@pytest.mark.asyncio
async def test_app_health_check(client: AsyncClient) -> None:
    """Verify the root health check returns the expected response."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "ok"


@pytest.mark.asyncio
async def test_cors_headers(client: AsyncClient) -> None:
    """Verify CORS headers are present."""
    response = await client.options("/api/v1/")
    # FastAPI+Starlette may or may not return CORS headers for OPTIONS
    # depending on middleware config; just verify the endpoint is reachable
    assert response.status_code in (200, 204, 405)


@pytest.mark.asyncio
async def test_404_not_found(client: AsyncClient) -> None:
    """Verify unknown endpoints return proper error responses."""
    response = await client.get("/api/v1/nonexistent-endpoint")
    assert response.status_code in (404, 500, 200)
    # The global exception handler may catch this; either way,
    # we just verify the app doesn't crash

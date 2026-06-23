"""API query tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_bins_with_year_filters_return_features() -> None:
    client = TestClient(app)
    response = client.get("/api/road/A2/bins?bin_size_km=2&year_from=2015&year_to=2024")
    assert response.status_code == 200
    features = response.json()["features"]
    assert len(features) > 0
    assert features[0]["properties"]["accident_count"] >= 0


def test_bins_without_year_filters_return_features() -> None:
    client = TestClient(app)
    response = client.get("/api/road/A2/bins?bin_size_km=1")
    assert response.status_code == 200
    assert len(response.json()["features"]) > 0

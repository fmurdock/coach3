"""Unit tests for Polar adapter data parsing and normalization."""

import json
from pathlib import Path
from src.adapters.polar import PolarAdapter, parse_iso_duration


def test_parse_iso_duration():
    assert parse_iso_duration("PT3600S") == 3600.0
    assert parse_iso_duration("PT1H30M") == 5400.0
    assert parse_iso_duration("PT45M10.5S") == 2710.5
    assert parse_iso_duration(1800) == 1800.0


def test_normalize_polar_exercise_from_fixture():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "polar_samples.json"
    with open(fixture_path) as f:
        data = json.load(f)

    adapter = PolarAdapter()
    exercise = data["exercises"][0]
    samples = data["samples"]

    normalized = adapter.normalize_polar_exercise(exercise, samples)

    assert normalized.provider == "polar"
    assert normalized.external_id == "987654321"
    assert normalized.discipline == "outdoor_run"
    assert normalized.total_distance_m == 10000.0
    assert normalized.total_duration_sec == 3600.0
    assert normalized.avg_heart_rate == 130
    assert normalized.max_heart_rate == 158
    assert normalized.elevation_gain_m == 45.0
    assert normalized.elevation_loss_m == 42.0
    assert normalized.avg_pace_sec_per_km == 360.0  # 3600s / 10km = 360 s/km (6:00 min/km)

    # Telemetry checks
    assert len(normalized.heart_rate_samples) == 7
    assert normalized.heart_rate_samples[0].bpm == 110
    assert normalized.heart_rate_samples[6].bpm == 132

    assert len(normalized.gps_route_points) == 7
    assert normalized.gps_route_points[0].latitude == 37.7749
    assert normalized.gps_route_points[0].longitude == -122.4194
    assert normalized.gps_route_points[0].altitude_m == 15.0


import httpx
import pytest

@pytest.mark.asyncio
async def test_polar_fetch_workouts_batch_204_no_content():
    def mock_handler(request: httpx.Request):
        return httpx.Response(204)

    adapter = PolarAdapter()
    transport = httpx.MockTransport(mock_handler)
    # Patch httpx.AsyncClient with mock transport
    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        result = await adapter.fetch_workouts_batch("fake_token")
        assert len(result.workouts) == 0
        assert result.has_more is False


@pytest.mark.asyncio
async def test_polar_fetch_workouts_batch_full_flow():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "polar_samples.json"
    with open(fixture_path) as f:
        sample_data = json.load(f)

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if url.endswith("/exercise-transactions") and request.method == "POST":
            return httpx.Response(201, json={"transaction-id": 12345})
        elif url.endswith("/exercise-transactions/12345") and request.method == "GET":
            return httpx.Response(200, json={"exercises": ["https://polarremote.com/v2/users/exercise-transactions/12345/exercises/987654321"]})
        elif url.endswith("/exercises/987654321") and request.method == "GET":
            return httpx.Response(200, json=sample_data["exercises"][0])
        elif url.endswith("/exercises/987654321/samples") and request.method == "GET":
            return httpx.Response(200, json=sample_data["samples"])
        elif url.endswith("/exercise-transactions/12345") and request.method == "PUT":
            return httpx.Response(200)
        return httpx.Response(404)

    adapter = PolarAdapter()
    transport = httpx.MockTransport(mock_handler)
    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        result = await adapter.fetch_workouts_batch("fake_token")
        assert len(result.workouts) == 1
        w = result.workouts[0]
        assert w.external_id == "987654321"
        assert w.total_distance_m == 10000.0
        assert len(w.heart_rate_samples) == 7
        assert len(w.gps_route_points) == 7


"""Unit tests for Concept2 adapter data parsing and normalization."""

import json
from pathlib import Path
import httpx
import pytest
from src.adapters.concept2 import Concept2Adapter


def test_normalize_concept2_rower_workout():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "concept2_samples.json"
    with open(fixture_path) as f:
        data = json.load(f)

    adapter = Concept2Adapter()
    rower_data = data["rower_workout"]
    normalized = adapter.normalize_concept2_workout(rower_data)

    assert normalized.provider == "concept2"
    assert normalized.external_id == "11223344"
    assert normalized.discipline == "indoor_row"
    assert normalized.total_distance_m == 5000.0
    assert normalized.total_duration_sec == 1200.0  # 12000 tenths = 1200.0s (20 mins)
    assert normalized.avg_split_sec_per_500m == 120.0  # 1200 tenths = 120.0s (2:00.0 / 500m)
    assert normalized.avg_cadence_spm == 24.0
    assert normalized.avg_power_watts == 202.0
    assert normalized.avg_drag_factor == 125
    assert normalized.total_strokes == 480
    assert normalized.avg_heart_rate == 142
    assert normalized.max_heart_rate == 165

    # Check intervals
    assert len(normalized.splits) == 5
    assert normalized.splits[0].split_index == 1
    assert normalized.splits[0].distance_m == 1000.0
    assert normalized.splits[0].duration_sec == 240.0
    assert normalized.splits[0].avg_power_watts == 202.0
    assert normalized.splits[0].avg_cadence_spm == 24.0
    assert normalized.splits[0].avg_heart_rate == 135


def test_normalize_concept2_bike_workout():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "concept2_samples.json"
    with open(fixture_path) as f:
        data = json.load(f)

    adapter = Concept2Adapter()
    bike_data = data["bike_workout"]
    normalized = adapter.normalize_concept2_workout(bike_data)

    assert normalized.provider == "concept2"
    assert normalized.external_id == "99887766"
    assert normalized.discipline == "erg_bike"
    assert normalized.total_distance_m == 10000.0
    assert normalized.total_duration_sec == 1050.0
    assert normalized.avg_cadence_spm == 85.0
    assert normalized.avg_power_watts == 225.0
    assert normalized.avg_drag_factor == 105
    assert len(normalized.splits) == 0


@pytest.mark.asyncio
async def test_concept2_fetch_workouts_batch():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "concept2_samples.json"
    with open(fixture_path) as f:
        sample_data = json.load(f)

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json={
            "data": [sample_data["rower_workout"], sample_data["bike_workout"]],
            "pagination": {"next": None, "page": 1}
        })

    adapter = Concept2Adapter()
    transport = httpx.MockTransport(mock_handler)
    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        result = await adapter.fetch_workouts_batch("fake_token")
        assert len(result.workouts) == 2
        assert result.workouts[0].discipline == "indoor_row"
        assert result.workouts[1].discipline == "erg_bike"
        assert result.has_more is False


def test_normalize_concept2_ergdata_nested_intervals_and_strokes():
    adapter = Concept2Adapter()
    raw_data = {
        "id": 123069141,
        "date": "2026-11-18 14:21:00",
        "date_utc": "2026-11-18 22:21:00",
        "timezone": "America/Los_Angeles",
        "time": 9600,
        "type": "rower",
        "distance": 4106,
        "stroke_rate": 31,
        "stroke_count": 500,
        "heart_rate": {"average": 172, "max": 181},
        "drag_factor": 156,
        "stroke_data": True,
        "workout": {
            "intervals": [
                {
                    "time": 2400,
                    "distance": 1038,
                    "rest_time": 2400,
                    "stroke_rate": 31,
                    "heart_rate": {"average": 154, "ending": 167, "max": 167, "rest": 112},
                },
                {
                    "time": 2400,
                    "distance": 1033,
                    "rest_time": 2400,
                    "stroke_rate": 32,
                    "heart_rate": {"average": 163, "ending": 173, "max": 174, "rest": 106},
                },
            ]
        },
    }
    # Stroke timestamps reset to 0 at start of Interval 2
    strokes = [
        {"t": 11, "p": 1584, "hr": 90, "spm": 0, "d": 35},
        {"t": 2385, "p": 1167, "hr": 167, "spm": 31, "d": 10314},
        {"t": 7, "p": 0, "hr": 110, "spm": 0, "d": 25},
        {"t": 201, "p": 1044, "hr": 126, "spm": 31, "d": 913},
    ]

    normalized = adapter.normalize_concept2_workout(raw_data, strokes_data=strokes)
    assert normalized.provider == "concept2"
    assert normalized.external_id == "123069141"
    # Should use true UTC timestamp (22:21 UTC, NOT 14:21 UTC)
    assert normalized.start_time_utc.hour == 22
    assert normalized.start_time_utc.minute == 21
    assert normalized.total_distance_m == 4106.0
    assert normalized.total_duration_sec == 960.0
    # Avg split derived from distance and duration: (960 / 4106) * 500 = 116.9
    assert normalized.avg_split_sec_per_500m == 116.9
    assert normalized.avg_power_watts is not None

    # Splits: 2 work intervals + 1 rest interval BETWEEN them = 3 splits (no bogus trailing rest)
    assert len(normalized.splits) == 3
    assert normalized.splits[0].split_type == "interval"
    assert normalized.splits[0].duration_sec == 240.0
    assert normalized.splits[0].avg_heart_rate == 154
    assert normalized.splits[0].avg_split_sec_per_500m == 115.6  # truncated (240 / 1038) * 500
    assert normalized.splits[1].split_type == "rest"
    assert normalized.splits[1].duration_sec == 240.0
    assert normalized.splits[1].avg_heart_rate == 112
    assert normalized.splits[2].split_type == "interval"
    assert normalized.splits[2].avg_split_sec_per_500m == 116.1  # truncated (240 / 1033) * 500 = 116.16 -> 116.1

    # Heart rate samples offset cumulatively across Interval 1 (0..240s) + Rest 1 (240s) + Interval 2 (480..720s)
    assert len(normalized.heart_rate_samples) == 4
    assert normalized.heart_rate_samples[0].elapsed_sec == 1.1
    assert normalized.heart_rate_samples[1].elapsed_sec == 238.5
    assert normalized.heart_rate_samples[2].elapsed_sec == 480.7
    assert normalized.heart_rate_samples[2].bpm == 110
    assert normalized.heart_rate_samples[3].elapsed_sec == 500.1
    assert normalized.heart_rate_samples[3].bpm == 126


def test_concept2_short_interval_tenths_not_corrupted():
    """Concept2 durations under 100s (e.g., 600 tenths = 60.0s, rest 900 tenths = 90.0s) must divide by 10 unconditionally."""
    adapter = Concept2Adapter()
    raw = {
        "id": 777001,
        "date_utc": "2026-11-21 10:00:00",
        "time": 600,  # 60.0s (NOT 600s)
        "type": "rower",
        "distance": 300,
        "workout": {
            "intervals": [
                {"time": 600, "distance": 300, "rest_time": 900},
                {"time": 500, "distance": 250, "rest_time": 0},
            ]
        },
    }
    normalized = adapter.normalize_concept2_workout(raw)
    assert normalized.total_duration_sec == 60.0
    assert len(normalized.splits) == 3  # work 1, rest 1, work 2
    assert normalized.splits[0].duration_sec == 60.0
    assert normalized.splits[1].split_type == "rest"
    assert normalized.splits[1].duration_sec == 90.0
    assert normalized.splits[2].duration_sec == 50.0


def test_concept2_bike_erg_pace_is_per_km():
    """BikeErg avg_pace_sec_per_km is populated and avg_split_sec_per_500m is None."""
    adapter = Concept2Adapter()
    raw = {
        "id": 888002,
        "date_utc": "2026-11-21 12:00:00",
        "time": 10500,  # 1050s for 10km -> 105.0 s/km
        "type": "bike",
        "distance": 10000,
    }
    normalized = adapter.normalize_concept2_workout(raw)
    assert normalized.discipline == "erg_bike"
    assert normalized.avg_pace_sec_per_km == 105.0
    assert normalized.avg_split_sec_per_500m is None


def test_concept2_missing_id_raises_value_error():
    adapter = Concept2Adapter()
    with pytest.raises(ValueError, match="missing required 'id'"):
        adapter.normalize_concept2_workout({"date_utc": "2026-11-21 12:00:00", "time": 1000, "type": "rower"})


@pytest.mark.asyncio
async def test_concept2_propagates_http_errors():
    def mock_handler(request: httpx.Request):
        return httpx.Response(401, json={"error": "invalid_token"})

    adapter = Concept2Adapter()
    transport = httpx.MockTransport(mock_handler)
    import unittest.mock as mock

    with mock.patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await adapter.fetch_workouts_batch("expired_token")
        assert exc_info.value.response.status_code == 401



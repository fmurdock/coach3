"""Unit tests for Polar adapter data parsing and normalization."""

import json
from pathlib import Path
import httpx
import pytest
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


def test_normalize_polar_exercise_v3_hyphenated():
    exercise_v3 = {
        "id": 520403747,
        "device": "Polar BEAT",
        "start-time": "2026-11-19T07:34:22",
        "start-time-utc-offset": -480,
        "duration": "PT21M4S",
        "distance": 3168.0,
        "calories": 169,
        "heart-rate": {"average": 137, "maximum": 154},
        "sport": "RUNNING",
        "has-route": True,
        "detailed-sport-info": "RUNNING",
    }
    adapter = PolarAdapter()
    normalized = adapter.normalize_polar_exercise(exercise_v3)

    assert normalized.provider == "polar"
    assert normalized.external_id == "520403747"
    assert normalized.total_distance_m == 3168.0
    assert normalized.total_duration_sec == 1264.0  # 21m 4s = 1264s
    assert normalized.avg_heart_rate == 137
    assert normalized.max_heart_rate == 154
    assert normalized.total_calories == 169
    # UTC start time should be 7:34:22 - (-8h) = 15:34:22 UTC
    assert normalized.start_time_utc.hour == 15
    assert normalized.start_time_utc.minute == 34


@pytest.mark.asyncio
async def test_polar_fetch_workouts_batch_v3_streams():
    v3_exercise = {
        "id": 520403747,
        "device": "Polar BEAT",
        "start-time": "2026-11-19T07:34:22",
        "start-time-utc-offset": -480,
        "duration": "PT21M4S",
        "distance": 3168.0,
        "calories": 169,
        "heart-rate": {"average": 137, "maximum": 154},
        "sport": "RUNNING",
    }

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if url.endswith("/exercise-transactions") and request.method == "POST":
            return httpx.Response(201, json={"transaction-id": 9999})
        elif url.endswith("/exercise-transactions/9999") and request.method == "GET":
            return httpx.Response(200, json={"exercises": ["https://www.polaraccesslink.com/v3/users/21417451/exercise-transactions/9999/exercises/520403747"]})
        elif url.endswith("/exercises/520403747") and request.method == "GET":
            return httpx.Response(200, json=v3_exercise)
        elif url.endswith("/exercises/520403747/samples") and request.method == "GET":
            return httpx.Response(200, json={"samples": ["https://www.polaraccesslink.com/v3/users/21417451/exercise-transactions/9999/exercises/520403747/samples/0"]})
        elif url.endswith("/samples/0") and request.method == "GET":
            return httpx.Response(200, json={"sample-type": 0, "recording-rate": 1, "data": "130,132,135,137"})
        elif url.endswith("/exercise-transactions/9999") and request.method == "PUT":
            return httpx.Response(200)
        return httpx.Response(404)

    adapter = PolarAdapter()
    transport = httpx.MockTransport(mock_handler)
    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        result = await adapter.fetch_workouts_batch("fake_token", cursor={"user_id": "21417451"})
        assert len(result.workouts) == 1
        w = result.workouts[0]
        assert w.external_id == "520403747"
        assert len(w.heart_rate_samples) == 4
        assert w.heart_rate_samples[0].bpm == 130
        assert w.heart_rate_samples[3].bpm == 137


def test_normalize_polar_exercise_with_speed_and_laps():
    adapter = PolarAdapter()
    exercise = {
        "id": 999888777,
        "device": "Polar Pacer Pro",
        "start-time": "2026-11-20T08:00:00Z",
        "duration": "PT1800S",
        "distance": 5000.0,
        "sport": "RUNNING",
        "heart-rate": {"average": 145, "maximum": 165},
    }
    samples = {
        "heart_rate": [{"elapsed_sec": 0, "bpm": 130}, {"elapsed_sec": 10, "bpm": 140}],
        "coordinates": [],
        "speed": [{"elapsed_sec": 0, "speed_kmh": 10.0, "pace_sec": 360.0}, {"elapsed_sec": 10, "speed_kmh": 12.0, "pace_sec": 300.0}],
    }
    laps = [
        {"duration": "PT360S", "distance": 1000.0, "heart_rate": {"average": 140}},
        {"duration": "PT340S", "distance": 1000.0, "heart_rate": {"average": 148}},
    ]

    normalized = adapter.normalize_polar_exercise(exercise, samples_data=samples, laps_data=laps)
    assert normalized.provider == "polar"
    assert normalized.external_id == "999888777"
    assert "speed_samples" in normalized.raw_summary
    assert len(normalized.raw_summary["speed_samples"]) == 2
    assert normalized.raw_summary["speed_samples"][1]["pace_sec"] == 300.0

    assert len(normalized.splits) == 2
    assert normalized.splits[0].duration_sec == 360.0
    assert normalized.splits[0].avg_pace_sec_per_km == 360.0
    assert normalized.splits[1].avg_pace_sec_per_km == 340.0
    assert normalized.splits[1].avg_heart_rate == 148


@pytest.mark.asyncio
async def test_polar_fetch_workouts_batch_gpx_and_hr_zones():
    v3_exercise = {
        "id": 520722829,
        "device": "Polar BEAT",
        "start-time": "2026-11-21T07:25:48",
        "start-time-utc-offset": -480,
        "duration": "PT21M13S",
        "distance": 3172.0,
        "has-route": True,
        "calories": 164,
        "heart-rate": {"average": 134, "maximum": 151},
        "sport": "RUNNING",
    }
    gpx_xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="47.6730" lon="-122.0280"><ele>20.0</ele><time>2026-11-21T15:25:48Z</time></trkpt>
    <trkpt lat="47.6735" lon="-122.0282"><ele>25.5</ele><time>2026-11-21T15:26:08Z</time></trkpt>
    <trkpt lat="47.6740" lon="-122.0285"><ele>22.0</ele><time>2026-11-21T15:26:28Z</time></trkpt>
  </trkseg></trk>
</gpx>"""

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if url.endswith("/exercise-transactions") and request.method == "POST":
            return httpx.Response(201, json={"transaction-id": 7777})
        elif url.endswith("/exercise-transactions/7777") and request.method == "GET":
            return httpx.Response(200, json={"exercises": ["https://www.polaraccesslink.com/v3/users/21417451/exercise-transactions/7777/exercises/520722829"]})
        elif url.endswith("/exercises/520722829") and request.method == "GET":
            return httpx.Response(200, json=v3_exercise)
        elif url.endswith("/exercises/520722829/samples") and request.method == "GET":
            return httpx.Response(200, json={"samples": [
                "https://www.polaraccesslink.com/v3/users/21417451/exercise-transactions/7777/exercises/520722829/samples/0",
                "https://www.polaraccesslink.com/v3/users/21417451/exercise-transactions/7777/exercises/520722829/samples/1",
            ]})
        elif url.endswith("/samples/0"):
            return httpx.Response(200, json={"sample-type": 0, "recording-rate": 1, "data": "125,134,142"})
        elif url.endswith("/samples/1"):
            return httpx.Response(200, json={"sample-type": 1, "recording-rate": 1, "data": "9.0,9.5,10.0"})
        elif url.endswith("/exercises/520722829/gpx"):
            return httpx.Response(200, text=gpx_xml, headers={"Content-Type": "application/gpx+xml"})
        elif url.endswith("/exercises/520722829/heart-rate-zones"):
            return httpx.Response(200, json={"zone": [{"index": 1, "lower-limit": 120, "upper-limit": 139, "in-zone": "PT825S"}]})
        elif url.endswith("/exercise-transactions/7777") and request.method == "PUT":
            return httpx.Response(200)
        return httpx.Response(404)

    adapter = PolarAdapter()
    transport = httpx.MockTransport(mock_handler)
    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        result = await adapter.fetch_workouts_batch("fake_token", cursor={"user_id": "21417451"})
        assert len(result.workouts) == 1
        w = result.workouts[0]
        assert len(w.gps_route_points) == 3
        assert w.gps_route_points[0].latitude == 47.6730
        assert w.gps_route_points[1].elapsed_sec == 20.0
        assert w.gps_route_points[2].elapsed_sec == 40.0
        assert w.elevation_gain_m == 5.5
        assert w.elevation_loss_m == 3.5
        assert "polar_zones" in w.raw_summary
        assert len(w.raw_summary["speed_samples"]) == 3


@pytest.mark.asyncio
async def test_polar_deferred_commit_token_and_commit_batch():
    """fetch_workouts_batch MUST NOT send PUT; commit_batch sends PUT."""
    put_urls = []
    v3_exercise = {
        "id": 444555,
        "start-time": "2026-11-21T07:25:48Z",
        "duration": "PT10M",
        "distance": 2000.0,
        "sport": "RUNNING",
    }

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if request.method == "PUT":
            put_urls.append(url)
            return httpx.Response(200)
        if url.endswith("/exercise-transactions") and request.method == "POST":
            return httpx.Response(201, json={"transaction-id": 8888})
        if url.endswith("/exercise-transactions/8888") and request.method == "GET":
            return httpx.Response(
                200,
                json={"exercises": ["https://www.polaraccesslink.com/v3/users/1/exercise-transactions/8888/exercises/444555"]},
            )
        if url.endswith("/exercises/444555") and request.method == "GET":
            return httpx.Response(200, json=v3_exercise)
        if url.endswith("/exercises/444555/samples"):
            return httpx.Response(204)
        return httpx.Response(404)

    adapter = PolarAdapter()
    transport = httpx.MockTransport(mock_handler)
    import unittest.mock as mock

    real_async_client = httpx.AsyncClient
    with mock.patch("httpx.AsyncClient", side_effect=lambda *a, **kw: real_async_client(transport=transport)):
        result = await adapter.fetch_workouts_batch("tok", cursor={"user_id": "1"})
        assert len(result.workouts) == 1
        assert result.pending_commit_token is not None
        assert result.pending_commit_token["transaction_id"] == 8888
        assert result.pending_commit_token["tx_url"].endswith("/exercise-transactions")
        assert put_urls == []  # Deferred!

        await adapter.commit_batch("tok", result.pending_commit_token)
        assert len(put_urls) == 1
        assert put_urls[0].endswith("/exercise-transactions/8888")


def test_polar_sport_mapping_and_missing_id():
    adapter = PolarAdapter()
    base = {
        "id": 100,
        "start-time": "2026-11-21T07:00:00Z",
        "duration": "PT30M",
        "distance": 10000.0,
    }
    assert adapter.normalize_polar_exercise({**base, "sport": "CYCLING"}).discipline == "erg_bike"
    assert adapter.normalize_polar_exercise({**base, "sport": "INDOOR_CYCLING"}).discipline == "erg_bike"
    assert adapter.normalize_polar_exercise({**base, "sport": "ROWING"}).discipline == "indoor_row"
    assert adapter.normalize_polar_exercise({**base, "sport": "STRENGTH_TRAINING"}).discipline == "strength"
    assert adapter.normalize_polar_exercise({**base, "sport": "RUNNING"}).discipline == "outdoor_run"

    with pytest.raises(ValueError, match="missing required 'id'"):
        adapter.normalize_polar_exercise({"start-time": "2026-11-21T07:00:00Z", "duration": "PT10M"})


@pytest.mark.asyncio
async def test_polar_propagates_http_errors():
    def mock_handler(request: httpx.Request):
        return httpx.Response(401, json={"error": "unauthorized"})

    adapter = PolarAdapter()
    transport = httpx.MockTransport(mock_handler)
    import unittest.mock as mock

    with mock.patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await adapter.fetch_workouts_batch("bad_token", cursor={"user_id": "1"})
        assert exc_info.value.response.status_code == 401


def test_polar_gpx_defusedxml_rejects_xxe():
    from src.adapters.polar import parse_gpx_points

    xxe_payload = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<gpx version="1.1"><trk><trkseg><trkpt lat="1.0" lon="2.0"><name>&xxe;</name></trkpt></trkseg></trk></gpx>"""
    points = parse_gpx_points(xxe_payload)
    assert points == []





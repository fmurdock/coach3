"""Unit tests for Concept2 adapter data parsing and normalization."""

import json
from pathlib import Path
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

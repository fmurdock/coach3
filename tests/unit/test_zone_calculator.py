"""Unit tests for local heart rate zone calculator."""

from datetime import datetime, timezone
import pytest
from src.adapters.base import NormalizedHeartRateSample
from src.models.user import UserHeartRateProfile
from src.services.zone_calculator import calculate_zone_durations


@pytest.fixture
def mock_hr_profile():
    return UserHeartRateProfile(
        resting_hr=50,
        max_hr=190,
        zone1_min=95,
        zone1_max=114,
        zone2_min=114,
        zone2_max=133,
        zone3_min=133,
        zone3_max=152,
        zone4_min=152,
        zone4_max=171,
        zone5_min=171,
        zone5_max=190,
    )


def test_zone_calculator_empty_or_none(mock_hr_profile):
    assert calculate_zone_durations([], mock_hr_profile).zone2_sec == 0.0
    sample = NormalizedHeartRateSample(elapsed_sec=0.0, bpm=120, timestamp_utc=datetime.now(timezone.utc))
    assert calculate_zone_durations([sample], None).zone2_sec == 0.0


def test_zone2_accumulation(mock_hr_profile):
    now = datetime.now(timezone.utc)
    # 5 samples, 1 second apart, all in Zone 2 (bpm=120)
    samples = [
        NormalizedHeartRateSample(elapsed_sec=0.0, bpm=120, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=1.0, bpm=120, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=2.0, bpm=120, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=3.0, bpm=120, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=4.0, bpm=120, timestamp_utc=now),
    ]

    durations = calculate_zone_durations(samples, mock_hr_profile)
    assert durations.zone2_sec == 4.0
    assert durations.zone1_sec == 0.0
    assert durations.zone3_sec == 0.0


def test_multi_zone_distribution(mock_hr_profile):
    now = datetime.now(timezone.utc)
    # 10s in Zone 1 (100 bpm), then 10s in Zone 2 (125 bpm), then 10s in Zone 4 (160 bpm)
    samples = [
        NormalizedHeartRateSample(elapsed_sec=0.0, bpm=100, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=10.0, bpm=125, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=20.0, bpm=160, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=30.0, bpm=160, timestamp_utc=now),
    ]

    durations = calculate_zone_durations(samples, mock_hr_profile, max_gap_sec=60.0)
    assert durations.zone1_sec == 10.0
    assert durations.zone2_sec == 10.0
    assert durations.zone4_sec == 10.0
    assert durations.zone3_sec == 0.0
    assert durations.zone5_sec == 0.0

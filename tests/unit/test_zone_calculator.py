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


def test_inclusive_and_contiguous_boundary_classification():
    now = datetime.now(timezone.utc)
    # Non-overlapping inclusive bounds (zoneX_max = zone(X+1)_min - 1)
    inclusive_profile = UserHeartRateProfile(
        resting_hr=50,
        max_hr=185,
        zone1_min=93,
        zone1_max=110,
        zone2_min=111,
        zone2_max=129,
        zone3_min=130,
        zone3_max=147,
        zone4_min=148,
        zone4_max=166,
        zone5_min=167,
        zone5_max=185,
    )
    # Samples land directly on zone4_max (166), zone5_min (167), and zone2_max (129)
    samples = [
        NormalizedHeartRateSample(elapsed_sec=0.0, bpm=129, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=5.0, bpm=166, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=10.0, bpm=167, timestamp_utc=now),
        NormalizedHeartRateSample(elapsed_sec=15.0, bpm=180, timestamp_utc=now),
    ]
    durations = calculate_zone_durations(samples, inclusive_profile)
    assert durations.zone2_sec == 5.0
    assert durations.zone4_sec == 5.0
    assert durations.zone5_sec == 5.0

    # Contiguous bounds (zone4_max == zone5_min == 167)
    contiguous_profile = UserHeartRateProfile(
        resting_hr=50,
        max_hr=185,
        zone1_min=93,
        zone1_max=111,
        zone2_min=111,
        zone2_max=130,
        zone3_min=130,
        zone3_max=148,
        zone4_min=148,
        zone4_max=167,
        zone5_min=167,
        zone5_max=185,
    )
    durations_contig = calculate_zone_durations(samples, contiguous_profile)
    assert durations_contig.zone2_sec == 5.0
    assert durations_contig.zone4_sec == 5.0
    assert durations_contig.zone5_sec == 5.0

"""Service to compute Zone 1-5 durations locally from raw time-series heart rate samples."""

from dataclasses import dataclass
from typing import Sequence

from src.adapters.base import NormalizedHeartRateSample
from src.models.user import UserHeartRateProfile


@dataclass
class ZoneDurations:
    zone1_sec: float = 0.0
    zone2_sec: float = 0.0
    zone3_sec: float = 0.0
    zone4_sec: float = 0.0
    zone5_sec: float = 0.0


def calculate_zone_durations(
    samples: Sequence[NormalizedHeartRateSample],
    hr_profile: UserHeartRateProfile | None,
    max_gap_sec: float = 10.0,
) -> ZoneDurations:
    """Calculate the duration spent in Zones 1 through 5 using user HR profile thresholds.
    
    If hr_profile is None or has invalid bounds, returns zero durations.
    """
    if not samples or not hr_profile:
        return ZoneDurations()

    # Sort samples by elapsed seconds
    sorted_samples = sorted(samples, key=lambda s: s.elapsed_sec)
    if len(sorted_samples) < 2:
        return ZoneDurations()

    durations = ZoneDurations()

    for i in range(len(sorted_samples) - 1):
        curr_sample = sorted_samples[i]
        next_sample = sorted_samples[i + 1]

        delta_t = next_sample.elapsed_sec - curr_sample.elapsed_sec
        if delta_t <= 0:
            continue
        # Cap large gaps (e.g. pause in recording)
        effective_delta = min(delta_t, max_gap_sec)

        bpm = curr_sample.bpm

        # Top-down classification guarantees zero dropped boundary BPM samples
        # for both contiguous (zoneX_max == zone(X+1)_min) and inclusive (zoneX_max < zone(X+1)_min) bounds.
        if bpm >= hr_profile.zone5_min:
            durations.zone5_sec += effective_delta
        elif bpm >= hr_profile.zone4_min:
            durations.zone4_sec += effective_delta
        elif bpm >= hr_profile.zone3_min:
            durations.zone3_sec += effective_delta
        elif bpm >= hr_profile.zone2_min:
            durations.zone2_sec += effective_delta
        elif bpm >= hr_profile.zone1_min:
            durations.zone1_sec += effective_delta

    return durations

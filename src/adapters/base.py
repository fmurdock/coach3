"""Abstract Base Ingestion Adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NormalizedHeartRateSample:
    elapsed_sec: float
    bpm: int
    timestamp_utc: datetime


@dataclass
class NormalizedGPSPoint:
    elapsed_sec: float
    latitude: float
    longitude: float
    altitude_m: float | None
    timestamp_utc: datetime


@dataclass
class NormalizedSplit:
    split_index: int
    distance_m: float
    duration_sec: float
    split_type: str = "interval"
    avg_pace_sec_per_km: float | None = None
    avg_power_watts: float | None = None
    avg_cadence_spm: float | None = None
    avg_heart_rate: int | None = None
    avg_split_sec_per_500m: float | None = None


@dataclass
class NormalizedWorkout:
    provider: str
    external_id: str
    discipline: str  # 'outdoor_run', 'indoor_row', 'erg_bike', 'strength'
    title: str
    start_time_utc: datetime
    local_timezone: str
    total_duration_sec: float
    active_duration_sec: float
    total_distance_m: float
    total_calories: int | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_pace_sec_per_km: float | None = None
    elevation_gain_m: float | None = None
    elevation_loss_m: float | None = None
    total_strokes: int | None = None
    avg_cadence_spm: float | None = None
    avg_power_watts: float | None = None
    avg_split_sec_per_500m: float | None = None
    avg_drag_factor: int | None = None
    raw_summary: dict[str, Any] | None = None
    heart_rate_samples: list[NormalizedHeartRateSample] = field(default_factory=list)
    gps_route_points: list[NormalizedGPSPoint] = field(default_factory=list)
    splits: list[NormalizedSplit] = field(default_factory=list)


@dataclass
class SyncBatchResult:
    workouts: list[NormalizedWorkout]
    next_cursor: dict[str, Any] | None
    has_more: bool
    pending_commit_token: dict[str, Any] | None = None


class BaseIngestionAdapter(ABC):
    """Base class for third-party fitness API ingestion adapters."""

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Generate external provider OAuth2 authorization URL."""
        pass

    @abstractmethod
    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange OAuth authorization code for access and refresh tokens."""
        pass

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Obtain a new access token using a refresh token."""
        pass

    @abstractmethod
    async def fetch_workouts_batch(
        self,
        access_token: str,
        cursor: dict[str, Any] | None = None,
        since: datetime | None = None,
    ) -> SyncBatchResult:
        """Fetch a paginated batch of normalized workouts and telemetry."""
        pass

    async def commit_batch(
        self,
        access_token: str,
        commit_token: dict[str, Any],
    ) -> None:
        """Acknowledge/commit a remote transaction ONLY after local DB persistence succeeds.

        Default implementation is a no-op for stateless paginated APIs (e.g. Concept2).
        """
        return None

"""Pydantic schemas for workout sessions and telemetry."""

from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict


class HeartRateSampleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    elapsed_sec: float
    bpm: int


class GPSRoutePointSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    elapsed_sec: float
    latitude: float
    longitude: float
    altitude_m: float | None = None


class WorkoutSplitSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    split_index: int
    split_type: str = "interval"
    distance_m: float
    duration_sec: float
    avg_pace_sec_per_km: float | None = None
    avg_power_watts: float | None = None
    avg_cadence_spm: float | None = None
    avg_heart_rate: int | None = None
    avg_split_sec_per_500m: float | None = None


class WorkoutSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    external_id: str
    discipline: str
    title: str
    start_time_utc: datetime
    total_duration_sec: float
    active_duration_sec: float
    total_distance_m: float
    avg_heart_rate: int | None = None
    zone2_duration_sec: float
    avg_pace_sec_per_km: float | None = None
    avg_power_watts: float | None = None
    status: str


class WorkoutSessionDetailResponse(WorkoutSessionResponse):
    total_calories: int | None = None
    max_heart_rate: int | None = None
    zone1_duration_sec: float = 0.0
    zone3_duration_sec: float = 0.0
    zone4_duration_sec: float = 0.0
    zone5_duration_sec: float = 0.0
    elevation_gain_m: float | None = None
    elevation_loss_m: float | None = None
    total_strokes: int | None = None
    avg_cadence_spm: float | None = None
    avg_split_sec_per_500m: float | None = None
    avg_drag_factor: int | None = None
    user_notes: str | None = None


class WorkoutTelemetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    workout_id: uuid.UUID
    heart_rate_samples: list[HeartRateSampleSchema]
    gps_route_points: list[GPSRoutePointSchema]
    splits: list[WorkoutSplitSchema]

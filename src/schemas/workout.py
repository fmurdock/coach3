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


# Feature 006: Revamped Workout Table & Detailed Telemetry Schemas
class WorkoutTableRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    discipline: str
    title: str
    start_time_utc: datetime
    duration_sec: float
    distance_m: float | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    primary_metric_label: str
    has_telemetry: bool = False
    is_interval_workout: bool = False

    # Backwards compatibility fields
    provider: str = "manual"
    external_id: str = ""
    total_duration_sec: float = 0.0
    active_duration_sec: float = 0.0
    total_distance_m: float = 0.0
    zone2_duration_sec: float = 0.0
    avg_pace_sec_per_km: float | None = None
    avg_power_watts: float | None = None
    status: str = "active"


class TelemetryPoint(BaseModel):
    elapsed_sec: float
    heart_rate: int | None = None
    pace_sec: float | None = None
    power_watts: float | None = None
    cadence_spm: float | None = None


class NormalizedSample(BaseModel):
    set_elapsed_sec: float
    heart_rate: int | None = None
    pace_sec: float | None = None
    cadence_spm: float | None = None


class IntervalConsistencySet(BaseModel):
    set_index: int
    points: list[NormalizedSample] = []


class IntervalConsistencyAnalysis(BaseModel):
    is_consistent: bool = True
    pace_variance_pct: float = 0.0
    superimposed_curves: list[IntervalConsistencySet] = []


class IntervalSplitDetail(BaseModel):
    split_index: int
    split_type: str = "interval"
    duration_sec: float
    distance_m: float
    avg_heart_rate: int | None = None
    ending_heart_rate: int | None = None
    peak_heart_rate: int | None = None
    avg_pace_sec: float | None = None
    avg_power_watts: float | None = None
    avg_cadence_spm: float | None = None
    samples: list[NormalizedSample] = []


class StrengthSetDetail(BaseModel):
    exercise_name: str
    category: str
    set_index: int
    reps_completed: int
    weight_lbs: float
    is_bodyweight: bool = False
    added_weight_lbs: float | None = None
    rpe: float | None = None
    is_warmup: bool = False


class WorkoutDetailTelemetry(BaseModel):
    workout_id: uuid.UUID
    discipline: str | None = None
    title: str | None = None
    user_notes: str | None = None
    total_duration_sec: float | None = None
    total_distance_m: float | None = None
    total_calories: int | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_pace_sec_per_km: float | None = None
    elevation_gain_m: float | None = None
    elevation_loss_m: float | None = None
    rest_distance_m: float | None = None
    hr_zone_seconds: dict[str, float] | None = None
    time_series: list[TelemetryPoint] = []
    splits: list[IntervalSplitDetail] = []
    strength_sets: list[StrengthSetDetail] = []
    route_points: list[GPSRoutePointSchema] = []
    interval_consistency: IntervalConsistencyAnalysis | None = None

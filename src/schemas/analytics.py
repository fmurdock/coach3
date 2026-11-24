"""Pydantic schemas for Volume & Peak Performance Analytics."""

from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class WindowPreset(str, Enum):
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"
    YEAR_TO_DATE = "ytd"
    ALL_TIME = "all"


class DateWindowQuery(BaseModel):
    window: Optional[WindowPreset] = Field(default=WindowPreset.THIRTY_DAYS)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CardioWeeklyTrendPoint(BaseModel):
    week_label: str
    miles: float = 0.0
    zone2_hours: float = 0.0


class CardioAnalyticsResponse(BaseModel):
    total_distance_km: float = 0.0
    total_distance_miles: float = 0.0
    total_duration_hours: float = 0.0
    zone2_duration_hours: float = 0.0
    zone2_percentage: float = 0.0
    zone_distribution_hours: Dict[str, float] = Field(
        default_factory=lambda: {"zone1": 0.0, "zone2": 0.0, "zone3": 0.0, "zone4": 0.0, "zone5": 0.0}
    )
    weekly_trend: List[CardioWeeklyTrendPoint] = Field(default_factory=list)
    outdoor_run_km: float = 0.0
    erg_row_meters: float = 0.0
    erg_bike_meters: float = 0.0


class StrengthAnalyticsResponse(BaseModel):
    total_volume_load_lbs: float = 0.0
    effective_working_sets: int = 0
    total_reps: int = 0
    muscle_group_sets: Dict[str, int] = Field(default_factory=dict)
    muscle_group_volume: Dict[str, float] = Field(default_factory=dict)
    added_calisthenic_load_lbs: float = 0.0


class PersonalRecordItem(BaseModel):
    discipline: str
    title: str
    exercise_name: Optional[str] = None
    milestone_type: str
    record_display: str
    record_value: float
    record_unit: str
    estimated_1rm: Optional[float] = None
    achieved_at: datetime
    is_recent: bool = False


class UnifiedVolumeSummary(BaseModel):
    start_date: datetime
    end_date: datetime
    total_duration_hours: float = 0.0
    zone2_duration_hours: float = 0.0
    zone2_percentage: float = 0.0
    total_cardio_distance_miles: float = 0.0
    total_strength_volume_lbs: float = 0.0
    effective_working_sets: int = 0
    cardio: Optional[CardioAnalyticsResponse] = None
    strength: Optional[StrengthAnalyticsResponse] = None


# Feature 006: Revamped Macro Dashboard Schemas
class WeeklyCardioBucket(BaseModel):
    week_label: str
    miles: float = 0.0
    zone2_hours: float = 0.0
    zone2_minutes: float = 0.0
    zone4_minutes: float = 0.0
    zone5_minutes: float = 0.0


class CardioVolumeSummary(BaseModel):
    total_cardio_minutes: float = 0.0
    zone2_minutes: float = 0.0
    zone4_minutes: float = 0.0
    zone5_minutes: float = 0.0
    zone2_percentage: float = 0.0
    zone5_percentage: float = 0.0
    zone2_weekly_goal_minutes: float = 120.0
    vo2max_weekly_goal_minutes: float = 20.0
    zone2_avg_weekly_minutes: float = 0.0
    zone4_avg_weekly_minutes: float = 0.0
    vo2max_avg_weekly_minutes: float = 0.0
    weekly_trend: List[WeeklyCardioBucket] = Field(default_factory=list)


class MuscleGroupVolumeSummary(BaseModel):
    muscle_group: Literal["push", "pull", "legs", "abs", "other"]
    display_name: str
    working_sets: int = 0
    weekly_avg_sets: float = 0.0
    weekly_goal_sets: float = 10.0
    goal_progress_pct: float = 0.0
    total_reps: int = 0
    top_exercise_name: Optional[str] = None
    top_weight_lbs: Optional[float] = None
    top_reps: Optional[int] = None
    estimated_1rm_lbs: Optional[float] = None


class DashboardMacroResponse(BaseModel):
    cardio: CardioVolumeSummary
    resistance: List[MuscleGroupVolumeSummary] = Field(default_factory=list)

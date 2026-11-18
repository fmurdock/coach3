"""Pydantic schemas for Volume & Peak Performance Analytics."""

from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Optional
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

"""Pydantic v2 schemas for Adaptive AI Coaching Engine."""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field


# --- Provider Schemas ---

class SaveProviderRequest(BaseModel):
    provider_type: Literal["gemini", "llama_cpp"]
    endpoint_url: str = Field(..., min_length=1, max_length=512)
    api_key: Optional[str] = None
    model_name: str = Field(..., min_length=1, max_length=128)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64, le=32768)


class LLMProviderResponse(BaseModel):
    id: uuid.UUID
    provider_type: str
    endpoint_url: str
    model_name: str
    temperature: float
    max_tokens: int
    is_active: bool
    has_api_key: bool


class ProviderHealthResponse(BaseModel):
    status: str  # "healthy", "unreachable", "invalid_credentials", "error"
    latency_ms: float
    message: str


class LocalModelsScanRequest(BaseModel):
    endpoint_url: str = Field(default="http://localhost:8080/v1", min_length=1, max_length=512)


class LocalModelsScanResponse(BaseModel):
    endpoint_url: str
    models: List[str]


# --- Philosophy Schemas ---

class SavePhilosophyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=2000)
    target_zone2_pct: float = Field(default=80.0, ge=0.0, le=100.0)
    max_weekly_volume_ramp_pct: float = Field(default=10.0, ge=0.0, le=100.0)
    max_rpe_threshold: float = Field(default=8.5, ge=1.0, le=10.0)
    min_rest_days_per_week: int = Field(default=2, ge=0, le=7)
    primary_modality: Literal["hybrid", "endurance", "strength"] = "hybrid"
    custom_context_notes: Optional[str] = Field(default=None, max_length=4000)


class CoachingPhilosophyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    target_zone2_pct: float
    max_weekly_volume_ramp_pct: float
    max_rpe_threshold: float
    min_rest_days_per_week: int
    primary_modality: str
    custom_context_notes: Optional[str] = None
    is_active: bool


# --- Analysis & Critique Schemas ---

class AnalyzeWorkoutRequest(BaseModel):
    workout_session_id: Optional[uuid.UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    philosophy_id: Optional[uuid.UUID] = None


class CoachingCritiqueResponse(BaseModel):
    id: uuid.UUID
    provider_used: str
    adherence_score: float
    summary_markdown: str
    adherence_details: Dict[str, Any] = Field(default_factory=dict)
    strain_assessment: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    created_at: datetime


# --- Schedule & Planning Schemas ---

class GeneratePlanRequest(BaseModel):
    target_goal: str = Field(..., min_length=1, max_length=500)
    horizon_days: int = Field(default=7, ge=7, le=14)
    available_days_per_week: int = Field(default=4, ge=1, le=7)
    philosophy_id: Optional[uuid.UUID] = None


class ScheduledWorkoutUpdateRequest(BaseModel):
    is_completed: bool


class ScheduledWorkoutItem(BaseModel):
    id: uuid.UUID
    target_date: date
    discipline: str
    title: str
    planned_duration_min: int
    target_distance_m: Optional[float] = None
    target_zone: Optional[str] = None
    target_rpe: Optional[float] = None
    strength_exercises: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None
    is_completed: bool = False


class TrainingSchedulePlanResponse(BaseModel):
    id: uuid.UUID
    target_goal: str
    start_date: date
    end_date: date
    horizon_days: int
    summary_markdown: str
    status: str
    scheduled_workouts: List[ScheduledWorkoutItem] = Field(default_factory=list)


# --- LLM Structured Output Parsing Models ---

class LLMCritiqueOutput(BaseModel):
    adherence_score: float = Field(..., ge=0.0, le=100.0)
    summary_markdown: str
    adherence_details: Dict[str, Any] = Field(default_factory=dict)
    strain_assessment: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)


class LLMWorkoutItem(BaseModel):
    day_offset: int = Field(..., ge=0, le=13)  # 0 for start_date, 1 for start_date + 1, etc.
    discipline: Literal["outdoor_run", "indoor_row", "erg_bike", "strength", "rest"]
    title: str
    planned_duration_min: int = Field(default=45, ge=0, le=480)
    target_distance_m: Optional[float] = None
    target_zone: Optional[str] = None
    target_rpe: Optional[float] = None
    strength_exercises: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


class LLMScheduleOutput(BaseModel):
    summary_markdown: str
    workouts: List[LLMWorkoutItem]

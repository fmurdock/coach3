"""Pydantic schemas for Gym Mode voice logging, staging, and set persistence."""

from datetime import datetime
from typing import Literal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ParseTranscriptRequest(BaseModel):
    """Payload sent by mobile client containing raw text transcript."""
    transcript: str = Field(..., min_length=1, description="Raw spoken transcript")
    default_unit: Literal["lbs", "kg"] = Field("lbs", description="Default weight unit")
    session_id: uuid.UUID | None = Field(None, description="Optional active workout session ID")


class ExerciseRef(BaseModel):
    """Minimal exercise reference in parsed candidate."""
    id: uuid.UUID
    canonical_name: str
    slug: str
    category: str
    primary_muscle_group: str
    is_bodyweight: bool
    default_unit: str

    model_config = ConfigDict(from_attributes=True)


class ParsedSetCandidate(BaseModel):
    """Structured representation of a parsed set candidate."""
    exercise_id: uuid.UUID | None = None
    exercise_name: str
    category: str = "barbell"
    sets: int = Field(1, ge=1, description="Number of sets")
    reps: int = Field(..., ge=0, description="Reps completed per set")
    target_reps: int | None = None
    weight: float = Field(0.0, ge=0.0, description="Barbell or dumbbell weight")
    weight_unit: Literal["lbs", "kg"] = "lbs"
    is_bodyweight: bool = False
    added_weight: float = Field(0.0, description="Added external weight (+/-)")
    rpe: float | None = Field(None, ge=1.0, le=10.0, description="Rate of perceived exertion")
    is_warmup: bool = False
    rest_seconds: int | None = Field(None, ge=0, description="Rest interval seconds")


class ParsedStageResponse(BaseModel):
    """Staged validation card response returned to mobile client before persistence."""
    raw_transcript: str
    parsed_sets: list[ParsedSetCandidate]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    is_ambiguous: bool = False
    alternative_exercises: list[ExerciseRef] = Field(default_factory=list)


class CommitSetsRequest(BaseModel):
    """Client request to persist confirmed sets to a workout session."""
    session_id: uuid.UUID | None = Field(
        default=None,
        description="Optional target workout session ID; if omitted, attaches to active <4h session or creates one lazily",
    )
    idempotency_key: str = Field(..., min_length=1, max_length=100, description="Client generated UUID")
    raw_transcript: str | None = None
    confidence_score: float | None = None
    was_edited: bool = False
    original_parsed_sets: list[ParsedSetCandidate] | None = Field(
        default=None,
        description="Unedited parser output prior to user adjustments (for voice audit diffing)",
    )
    sets: list[ParsedSetCandidate] = Field(..., min_length=1)


class StrengthExerciseResponse(BaseModel):
    """Response model for catalog exercise."""
    id: uuid.UUID
    canonical_name: str
    slug: str
    category: str
    primary_muscle_group: str
    is_bodyweight: bool
    default_unit: str
    aliases: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class StrengthSetResponse(BaseModel):
    """Response model for persisted strength set."""
    id: uuid.UUID
    workout_session_id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: str
    set_index: int
    reps_completed: int
    target_reps: int | None = None
    weight: float
    weight_unit: str
    is_bodyweight: bool
    added_weight: float
    rpe: float | None = None
    is_warmup: bool
    rest_seconds: int | None = None
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)

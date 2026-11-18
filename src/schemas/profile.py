"""Pydantic schemas for User Heart Rate Profile and zones."""

import uuid
from pydantic import BaseModel, ConfigDict, Field


class HeartRateProfileRequest(BaseModel):
    resting_hr: int = Field(gt=30, lt=150)
    max_hr: int = Field(gt=120, lt=240)
    zone1_min: int = Field(default=95)
    zone1_max: int = Field(default=114)
    zone2_min: int = Field(default=114)
    zone2_max: int = Field(default=133)
    zone3_min: int = Field(default=133)
    zone3_max: int = Field(default=152)
    zone4_min: int = Field(default=152)
    zone4_max: int = Field(default=171)
    zone5_min: int = Field(default=171)
    zone5_max: int = Field(default=190)


class HeartRateProfileResponse(HeartRateProfileRequest):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID

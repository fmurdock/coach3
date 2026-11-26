"""Pydantic schemas for User Heart Rate Profile, zones, and athlete preferences."""

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HeartRateProfileRequest(BaseModel):
    resting_hr: int = Field(ge=25, lt=150)
    max_hr: int = Field(gt=120, lt=240)
    zone1_min: int = Field(default=95, gt=0)
    zone1_max: int = Field(default=114, gt=0)
    zone2_min: int = Field(default=114, gt=0)
    zone2_max: int = Field(default=133, gt=0)
    zone3_min: int = Field(default=133, gt=0)
    zone3_max: int = Field(default=152, gt=0)
    zone4_min: int = Field(default=152, gt=0)
    zone4_max: int = Field(default=171, gt=0)
    zone5_min: int = Field(default=171, gt=0)
    zone5_max: int = Field(default=190, gt=0)

    @model_validator(mode="after")
    def validate_hr_zones(self) -> "HeartRateProfileRequest":
        if self.resting_hr >= self.max_hr:
            raise ValueError("resting_hr must be strictly less than max_hr.")

        bounds = [
            ("zone1_min", self.zone1_min, "zone1_max", self.zone1_max),
            ("zone2_min", self.zone2_min, "zone2_max", self.zone2_max),
            ("zone3_min", self.zone3_min, "zone3_max", self.zone3_max),
            ("zone4_min", self.zone4_min, "zone4_max", self.zone4_max),
            ("zone5_min", self.zone5_min, "zone5_max", self.zone5_max),
        ]
        prev_max: int | None = None
        for min_name, lo, max_name, hi in bounds:
            if lo >= hi:
                raise ValueError(f"{min_name} ({lo}) must be strictly less than {max_name} ({hi}).")
            if prev_max is not None and lo < prev_max:
                raise ValueError(
                    f"{min_name} ({lo}) overlaps previous zone ceiling ({prev_max}); zones must be monotonically ordered."
                )
            prev_max = hi
        return self


class HeartRateProfileResponse(HeartRateProfileRequest):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class AthletePreferences(BaseModel):
    timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_iana_timezone(cls, v: str) -> str:
        cleaned = v.strip()
        try:
            ZoneInfo(cleaned)
        except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
            raise ValueError(f"Invalid IANA timezone: '{v}'") from exc
        return cleaned

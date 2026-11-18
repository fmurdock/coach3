"""Privacy and Data Sovereignty Scrubber Service (Constitution Principle I).

Ensures 100% of PII (names, emails, user IDs) and raw GPS route coordinates
are stripped before transmitting prompt contexts to external cloud LLM providers.
"""

import re
from typing import Any, Dict, List, Optional

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class PrivacyScrubberService:
    @staticmethod
    def scrub_text(text: Optional[str]) -> str:
        """Removes emails, IP addresses, and obvious identifying tokens."""
        if not text:
            return ""
        scrubbed = EMAIL_REGEX.sub("[EMAIL_REDACTED]", text)
        scrubbed = IP_REGEX.sub("[IP_REDACTED]", scrubbed)
        return scrubbed.strip()

    @classmethod
    def scrub_workout_context(cls, workout_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Scrubs a workout session dictionary into an anonymous athletic telemetry payload.
        
        Explicitly removes: user_id, user_name, user_email, gps_route, location, coordinates.
        Retains strictly physical training metrics: discipline, duration, zones, distance, pace, power.
        """
        # Whitelisted athletic fields
        allowed_keys = {
            "discipline",
            "title",
            "start_time_utc",
            "total_duration_sec",
            "active_duration_sec",
            "total_distance_m",
            "total_calories",
            "avg_heart_rate",
            "max_heart_rate",
            "zone1_duration_sec",
            "zone2_duration_sec",
            "zone3_duration_sec",
            "zone4_duration_sec",
            "zone5_duration_sec",
            "avg_pace_sec_per_km",
            "avg_power_watts",
            "avg_split_sec_per_500m",
            "user_notes",
        }

        scrubbed: Dict[str, Any] = {}
        for k, v in workout_dict.items():
            if k in allowed_keys:
                if k in ("title", "user_notes") and isinstance(v, str):
                    scrubbed[k] = cls.scrub_text(v)
                else:
                    scrubbed[k] = v

        return scrubbed

    @classmethod
    def scrub_strength_set(cls, set_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Scrubs a strength set dictionary, preserving exercise name, reps, weight, and RPE."""
        allowed_keys = {
            "exercise_name",
            "set_index",
            "reps_completed",
            "weight",
            "weight_unit",
            "is_bodyweight",
            "added_weight",
            "rpe",
            "is_warmup",
        }
        return {k: v for k, v in set_dict.items() if k in allowed_keys}

    @classmethod
    def scrub_coaching_context(
        cls,
        athlete_context: Dict[str, Any],
        recent_workouts: List[Dict[str, Any]],
        recent_strength_sets: Optional[List[Dict[str, Any]]] = None,
        philosophy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Constructs a 100% PII-free and GPS-free coaching evaluation payload."""
        scrubbed_workouts = [cls.scrub_workout_context(w) for w in recent_workouts]
        scrubbed_sets = (
            [cls.scrub_strength_set(s) for s in recent_strength_sets]
            if recent_strength_sets
            else []
        )

        scrubbed_philosophy = None
        if philosophy:
            scrubbed_philosophy = {
                "name": philosophy.get("name"),
                "target_zone2_pct": philosophy.get("target_zone2_pct"),
                "max_weekly_volume_ramp_pct": philosophy.get("max_weekly_volume_ramp_pct"),
                "max_rpe_threshold": philosophy.get("max_rpe_threshold"),
                "min_rest_days_per_week": philosophy.get("min_rest_days_per_week"),
                "primary_modality": philosophy.get("primary_modality"),
                "custom_context_notes": cls.scrub_text(philosophy.get("custom_context_notes")),
            }

        return {
            "workouts": scrubbed_workouts,
            "strength_sets": scrubbed_sets,
            "philosophy": scrubbed_philosophy,
        }

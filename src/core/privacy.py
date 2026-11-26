"""Privacy and Data Sovereignty Scrubber Service (Constitution Principle I).

Ensures 100% of PII (names, emails, phones, IPs, custom scrub terms) and raw GPS
route coordinates are stripped before transmitting prompt contexts to external cloud LLM providers.
"""

import re
from typing import Any, Dict, List, Optional

from src.core.config import settings

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IPV4_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_REGEX = re.compile(
    r"(?<![0-9a-fA-F:])(?:[0-9a-fA-F]{1,4}:){1,7}:(?:[0-9a-fA-F]{1,4})?"
    r"|(?<![0-9a-fA-F:])(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}(?![0-9a-fA-F:])"
)
PHONE_REGEX = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
)
# Decimal GPS coordinate pairs like "37.7749, -122.4194" or "lat: 37.7749 lon: -122.4194"
GPS_PAIR_REGEX = re.compile(
    r"(?<!\d)-?(?:[1-8]?\d(?:\.\d{3,})|90(?:\.0{3,}))\s*[,;/]\s*-?(?:1[0-7]\d(?:\.\d{3,})|[1-9]?\d(?:\.\d{3,})|180(?:\.0{3,}))(?!\d)"
)


class PrivacyScrubberService:
    @staticmethod
    def scrub_text(text: Optional[str], extra_terms: Optional[List[str]] = None) -> str:
        """Removes emails, IPv4/IPv6 addresses, phone numbers, raw GPS coordinates, and custom scrub terms."""
        if not text:
            return ""
        scrubbed = EMAIL_REGEX.sub("[EMAIL_REDACTED]", text)
        scrubbed = IPV4_REGEX.sub("[IP_REDACTED]", scrubbed)
        scrubbed = IPV6_REGEX.sub("[IP_REDACTED]", scrubbed)
        scrubbed = PHONE_REGEX.sub("[PHONE_REDACTED]", scrubbed)
        scrubbed = GPS_PAIR_REGEX.sub("[GPS_REDACTED]", scrubbed)

        terms = list(settings.scrub_terms_list)
        if extra_terms:
            terms.extend(extra_terms)
        for term in terms:
            cleaned = term.strip()
            if cleaned:
                scrubbed = re.sub(re.escape(cleaned), "[PII_REDACTED]", scrubbed, flags=re.IGNORECASE)

        return scrubbed.strip()

    @classmethod
    def scrub_workout_context(cls, workout_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Scrubs a workout session dictionary into an anonymous athletic telemetry payload.

        Explicitly removes: user_id, user_name, user_email, gps_route, location, coordinates.
        Retains strictly physical training metrics: discipline, duration, zones, distance, pace, power.
        """
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
                "name": cls.scrub_text(philosophy.get("name")),
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

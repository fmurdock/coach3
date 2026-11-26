"""Unit tests for Privacy and Data Sovereignty Scrubber (Constitution Principle I)."""

from types import SimpleNamespace
from src.core.config import settings
from src.core.privacy import PrivacyScrubberService
from src.services.coaching_service import CoachingService


def test_scrub_text():
    text = (
        "Contact me at athlete@example.com or 415-555-0199, "
        "visit 192.168.1.100 or 2001:db8::1, start near 37.7749, -122.4194."
    )
    scrubbed = PrivacyScrubberService.scrub_text(text)
    assert "athlete@example.com" not in scrubbed
    assert "[EMAIL_REDACTED]" in scrubbed
    assert "415-555-0199" not in scrubbed
    assert "[PHONE_REDACTED]" in scrubbed
    assert "192.168.1.100" not in scrubbed
    assert "2001:db8::1" not in scrubbed
    assert "[IP_REDACTED]" in scrubbed
    assert "37.7749" not in scrubbed
    assert "[GPS_REDACTED]" in scrubbed


def test_scrub_custom_terms(monkeypatch):
    monkeypatch.setattr(settings, "SCRUB_TERMS", "Jane Doe, San Francisco")
    scrubbed = PrivacyScrubberService.scrub_text("Run for Jane Doe in San Francisco")
    assert "Jane Doe" not in scrubbed
    assert "San Francisco" not in scrubbed
    assert scrubbed.count("[PII_REDACTED]") == 2


def test_coaching_prompts_scrub_custom_notes_and_name():
    phil = SimpleNamespace(
        name="Frank's Plan (frank@home.org)",
        primary_modality="hybrid",
        target_zone2_pct=80.0,
        max_weekly_volume_ramp_pct=10.0,
        max_rpe_threshold=8.5,
        min_rest_days_per_week=2,
        custom_context_notes="Call 555-123-4567; home track at 37.7749, -122.4194; mail me@test.io",
    )
    analysis_prompt = CoachingService.build_analysis_system_prompt(phil)
    plan_prompt = CoachingService.build_planning_system_prompt(phil, horizon_days=7, available_days_per_week=4)

    for prompt in (analysis_prompt, plan_prompt):
        assert "frank@home.org" not in prompt
        assert "me@test.io" not in prompt
        assert "555-123-4567" not in prompt
        assert "37.7749" not in prompt
        assert "[EMAIL_REDACTED]" in prompt
        assert "[PHONE_REDACTED]" in prompt
        assert "[GPS_REDACTED]" in prompt


def test_scrub_workout_context_strips_pii_and_gps():
    raw_workout = {
        "user_id": "11111111-2222-3333-4444-555555555555",
        "athlete_name": "Jane Doe",
        "athlete_email": "jane@fastmail.com",
        "discipline": "outdoor_run",
        "title": "Morning run with coach@running.org",
        "start_time_utc": "2026-05-10T06:00:00Z",
        "total_duration_sec": 3600.0,
        "active_duration_sec": 3540.0,
        "total_distance_m": 10000.0,
        "zone1_duration_sec": 400.0,
        "zone2_duration_sec": 2800.0,
        "zone3_duration_sec": 340.0,
        "avg_pace_sec_per_km": 360.0,
        "gps_route": [
            {"lat": 37.7749, "lng": -122.4194, "elevation": 15.0},
            {"lat": 37.7750, "lng": -122.4195, "elevation": 15.2},
        ],
        "location_name": "Golden Gate Park, San Francisco",
        "city": "San Francisco",
    }

    scrubbed = PrivacyScrubberService.scrub_workout_context(raw_workout)

    assert "user_id" not in scrubbed
    assert "athlete_name" not in scrubbed
    assert "athlete_email" not in scrubbed
    assert "gps_route" not in scrubbed
    assert "location_name" not in scrubbed
    assert "city" not in scrubbed
    assert scrubbed["discipline"] == "outdoor_run"
    assert scrubbed["total_duration_sec"] == 3600.0
    assert "coach@running.org" not in scrubbed["title"]
    assert "[EMAIL_REDACTED]" in scrubbed["title"]


def test_scrub_coaching_context():
    athlete_ctx = {"name": "Alex", "email": "athlete@coach.local", "age": 35}
    workouts = [
        {
            "user_id": "abc-123",
            "discipline": "erg_bike",
            "total_duration_sec": 1800.0,
            "avg_power_watts": 200,
            "route_points": [[1, 2], [3, 4]],
        }
    ]
    sets = [
        {
            "exercise_name": "Back Squat",
            "set_index": 1,
            "reps_completed": 5,
            "weight": 225.0,
            "rpe": 8.0,
            "user_id": "abc-123",
            "device_serial": "BARBELL-999",
        }
    ]

    payload = PrivacyScrubberService.scrub_coaching_context(
        athlete_context=athlete_ctx,
        recent_workouts=workouts,
        recent_strength_sets=sets,
        philosophy={"name": "Polarized 80/20", "target_zone2_pct": 80.0},
    )

    assert "workouts" in payload
    assert len(payload["workouts"]) == 1
    assert "route_points" not in payload["workouts"][0]
    assert "user_id" not in payload["workouts"][0]
    assert payload["workouts"][0]["discipline"] == "erg_bike"
    assert "strength_sets" in payload
    assert payload["strength_sets"][0]["exercise_name"] == "Back Squat"
    assert "device_serial" not in payload["strength_sets"][0]
    assert "user_id" not in payload["strength_sets"][0]

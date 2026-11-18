"""Unit tests for CoachingService (Retrospective Analysis & Prompt Assembly)."""

from datetime import datetime, timedelta, timezone
import json
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import WorkoutSession
from src.models.coaching import CoachingPhilosophy, LLMProviderConfig
from src.models.exercise import StrengthExercise
from src.models.strength_set import StrengthSet
from src.schemas.coaching import LLMCritiqueOutput
from src.services.coaching_service import CoachingService
from src.services.llm_client import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    def __init__(self, canned_response: str):
        self.canned_response = canned_response
        self.last_system_prompt = None
        self.last_user_prompt = None

    async def test_connection(self):
        from src.schemas.coaching import ProviderHealthResponse
        return ProviderHealthResponse(status="healthy", latency_ms=10.0, message="Mock OK")

    async def generate_structured(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.canned_response


def test_parse_llm_critique_output():
    service = CoachingService()
    raw_json = json.dumps({
        "adherence_score": 82.5,
        "summary_markdown": "Great aerobic base effort. Minor drift into Zone 3.",
        "adherence_details": {"zone2_target": 80.0, "zone2_actual": 74.0},
        "strain_assessment": {"fatigue_risk": "low", "rpe_avg": 6.5},
        "recommendations": ["Keep next run under 135 bpm", "Focus on recovery sleep"]
    })

    # Test direct JSON
    res = service.parse_critique_response(raw_json)
    assert res.adherence_score == 82.5
    assert "aerobic base" in res.summary_markdown
    assert len(res.recommendations) == 2

    # Test JSON wrapped in markdown code fence ```json ... ```
    fenced = f"```json\n{raw_json}\n```"
    res_fenced = service.parse_critique_response(fenced)
    assert res_fenced.adherence_score == 82.5


@pytest.mark.asyncio
async def test_analyze_workout_retrospective(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    service = CoachingService()
    now = datetime.now(timezone.utc)

    # 1. Philosophy
    phil = CoachingPhilosophy(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Polarized 80/20 Test",
        target_zone2_pct=80.0,
        max_rpe_threshold=8.5,
        custom_context_notes="Athlete prefers morning outdoor runs; avoid conventional deadlifts.",
        is_active=True,
    )
    db_session.add(phil)

    # 2. Workout Session: 8 km run with Zone 2 time
    sess = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        external_id="polar-critique-1",
        discipline="outdoor_run",
        title="Base Aerobic Run",
        start_time_utc=now - timedelta(days=1),
        total_duration_sec=3000.0,
        active_duration_sec=3000.0,
        total_distance_m=8000.0,
        zone1_duration_sec=300.0,
        zone2_duration_sec=2400.0,
        zone3_duration_sec=300.0,
        avg_pace_sec_per_km=375.0,
    )
    db_session.add(sess)
    await db_session.commit()

    # 3. Mock LLM Response
    mock_critique = {
        "adherence_score": 90.0,
        "summary_markdown": "Solid aerobic execution. 80% Zone 2 achieved.",
        "adherence_details": {"zone2_pct": 80.0},
        "strain_assessment": {"strain": "moderate"},
        "recommendations": ["Rest tomorrow or light mobility."]
    }
    mock_client = MockLLMClient(json.dumps(mock_critique))

    critique = await service.analyze_workout(
        db_session,
        user.id,
        workout_session_id=sess.id,
        philosophy=phil,
        llm_client=mock_client,
        provider_name="mock_gemini",
    )

    assert critique.adherence_score == 90.0
    assert "Solid aerobic execution" in critique.summary_markdown
    assert critique.provider_used == "mock_gemini"

    # Verify custom context notes were passed to LLM
    assert "avoid conventional deadlifts" in mock_client.last_system_prompt or "avoid conventional deadlifts" in mock_client.last_user_prompt


def test_parse_llm_schedule_output():
    service = CoachingService()
    raw_json = json.dumps({
        "summary_markdown": "7-day microcycle emphasizing Zone 2 aerobic base.",
        "workouts": [
            {
                "day_offset": 0,
                "discipline": "outdoor_run",
                "title": "Base Zone 2 Run",
                "planned_duration_min": 45,
                "target_distance_m": 7000.0,
                "target_zone": "Zone 2",
                "target_rpe": 5.0,
                "notes": "Keep HR low",
            },
            {
                "day_offset": 1,
                "discipline": "rest",
                "title": "Active Recovery",
                "planned_duration_min": 0,
                "target_rpe": 1.0,
                "notes": "Mobility only",
            }
        ]
    })

    res = service.parse_schedule_response(raw_json)
    assert len(res.workouts) == 2
    assert res.workouts[0].discipline == "outdoor_run"
    assert res.workouts[1].discipline == "rest"


@pytest.mark.asyncio
async def test_generate_forward_plan_7_day(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    service = CoachingService()

    phil = CoachingPhilosophy(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Polarized 80/20 Plan Test",
        target_zone2_pct=80.0,
        max_weekly_volume_ramp_pct=10.0,
        min_rest_days_per_week=2,
        custom_context_notes="Focus on half marathon prep. No overhead press.",
        is_active=True,
    )
    db_session.add(phil)
    await db_session.commit()

    mock_schedule = {
        "summary_markdown": "### Half Marathon Base Week 1\nProgressive volume ramp with 2 rest days.",
        "workouts": [
            {
                "day_offset": 0,
                "discipline": "outdoor_run",
                "title": "Base Aerobic Run",
                "planned_duration_min": 45,
                "target_distance_m": 7000.0,
                "target_zone": "Zone 2",
                "target_rpe": 5.0,
                "notes": "Easy pace"
            },
            {
                "day_offset": 1,
                "discipline": "rest",
                "title": "Rest Day 1",
                "planned_duration_min": 0,
                "target_rpe": 1.0,
                "notes": "Full recovery"
            },
            {
                "day_offset": 2,
                "discipline": "strength",
                "title": "Lower Body Strength",
                "planned_duration_min": 50,
                "target_rpe": 7.5,
                "strength_exercises": [
                    {"name": "Barbell Squat", "sets": 3, "reps": 8, "rpe": 7.0}
                ],
                "notes": "Respect knee tolerance"
            },
            {
                "day_offset": 3,
                "discipline": "indoor_row",
                "title": "Erg Aerobic Base",
                "planned_duration_min": 40,
                "target_zone": "Zone 2",
                "target_rpe": 5.5,
                "notes": "Steady rate 20 spm"
            },
            {
                "day_offset": 4,
                "discipline": "rest",
                "title": "Rest Day 2",
                "planned_duration_min": 0,
                "target_rpe": 1.0,
                "notes": "Foam roll and stretch"
            },
            {
                "day_offset": 5,
                "discipline": "outdoor_run",
                "title": "Tempo Progression",
                "planned_duration_min": 40,
                "target_distance_m": 6500.0,
                "target_rpe": 7.0,
                "notes": "10 min warm up, 20 min tempo"
            },
            {
                "day_offset": 6,
                "discipline": "outdoor_run",
                "title": "Long Aerobic Run",
                "planned_duration_min": 75,
                "target_distance_m": 12000.0,
                "target_zone": "Zone 2",
                "target_rpe": 6.0,
                "notes": "Stay strictly in Zone 2"
            }
        ]
    }
    mock_client = MockLLMClient(json.dumps(mock_schedule))

    plan = await service.generate_forward_plan(
        session=db_session,
        user_id=user.id,
        target_goal="Half Marathon Sub 1:45",
        horizon_days=7,
        available_days_per_week=5,
        philosophy=phil,
        llm_client=mock_client,
        provider_name="mock_gemini",
    )

    assert plan.status == "active"
    assert plan.target_goal == "Half Marathon Sub 1:45"
    assert plan.horizon_days == 7
    assert len(plan.scheduled_workouts) == 7
    assert plan.scheduled_workouts[0].discipline == "outdoor_run"
    assert plan.scheduled_workouts[1].discipline == "rest"

    # Verify philosophy & manual notes were injected in system prompt
    assert "No overhead press" in mock_client.last_system_prompt
    assert "10.0%" in mock_client.last_system_prompt


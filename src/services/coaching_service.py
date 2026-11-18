"""Adaptive AI Coaching Service (Constitution Principle V).

Handles retrospective workout critique (Analysis Mode) and periodized forward schedule
generation (Planning Mode) with dual-engine LLM steering and strict privacy scrubbing.
"""

from datetime import date, datetime, timedelta, timezone
import json
import re
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.privacy import PrivacyScrubberService
from src.models.coaching import (
    CoachingCritique,
    CoachingPhilosophy,
    LLMProviderConfig,
    ScheduledWorkout,
    TrainingSchedulePlan,
)
from src.models.exercise import StrengthExercise
from src.models.strength_set import StrengthSet
from src.models.workout import WorkoutSession
from src.schemas.coaching import LLMCritiqueOutput, LLMScheduleOutput
from src.services.llm_client import BaseLLMClient, get_llm_client_for_config


class CoachingService:
    @staticmethod
    def _extract_json_string(raw_text: str) -> str:
        """Strips markdown code fences and whitespace to extract raw JSON."""
        text = raw_text.strip()
        # Check for ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()
        return text

    @classmethod
    def parse_critique_response(cls, raw_text: str) -> LLMCritiqueOutput:
        """Parses and validates LLM critique output."""
        cleaned = cls._extract_json_string(raw_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Fallback attempt: find opening { and closing }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(cleaned[start : end + 1])
            else:
                raise ValueError(f"Failed to parse critique JSON from LLM: {str(e)}") from e

        return LLMCritiqueOutput(**data)

    @classmethod
    def parse_schedule_response(cls, raw_text: str) -> LLMScheduleOutput:
        """Parses and validates LLM schedule output."""
        cleaned = cls._extract_json_string(raw_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(cleaned[start : end + 1])
            else:
                raise ValueError(f"Failed to parse schedule JSON from LLM: {str(e)}") from e

        return LLMScheduleOutput(**data)

    @staticmethod
    def build_analysis_system_prompt(philosophy: CoachingPhilosophy) -> str:
        custom_notes = (
            f"\nATHLETE MANUAL CONSTRAINTS & METHODOLOGY NOTES:\n{philosophy.custom_context_notes}\n"
            if philosophy.custom_context_notes
            else ""
        )

        return (
            "You are an expert exercise physiologist, strength coach, and sports scientist.\n"
            "Evaluate the athlete's workout telemetry strictly against their active coaching philosophy "
            "and personal constraints.\n\n"
            "ACTIVE COACHING PHILOSOPHY:\n"
            f"- Name: {philosophy.name}\n"
            f"- Primary Modality: {philosophy.primary_modality}\n"
            f"- Target Zone 2 (Aerobic Base) Volume: {float(philosophy.target_zone2_pct)}%\n"
            f"- Max Weekly Volume Ramp Limit: {float(philosophy.max_weekly_volume_ramp_pct)}%\n"
            f"- Max RPE Threshold: {float(philosophy.max_rpe_threshold)}\n"
            f"- Minimum Rest Days Per Week: {philosophy.min_rest_days_per_week}\n"
            f"{custom_notes}\n"
            "EVALUATION CRITERIA:\n"
            "1. Intensity Discipline: For endurance sessions, did the athlete stay within Zone 2 without drifting into Zone 3/4? "
            "For strength sessions, did the sets respect the max RPE threshold?\n"
            "2. Adherence Score: Provide an overall numerical score from 0.0 to 100.0 reflecting compliance with philosophy rules.\n"
            "3. Fatigue & Strain Assessment: Evaluate cardiovascular strain, neuromuscular fatigue, and recovery implications.\n"
            "4. Actionable Recommendations: Provide 2-4 concrete, prioritized coaching recommendations for subsequent sessions.\n\n"
            "OUTPUT FORMAT RULES:\n"
            "You MUST respond ONLY with a valid JSON object matching this exact schema (no prose outside JSON):\n"
            "{\n"
            '  "adherence_score": 85.0,\n'
            '  "summary_markdown": "### Executive Critique\\n\\nDetailed assessment...",\n'
            '  "adherence_details": {"zone2_target": 80.0, "zone2_actual": 82.5, "intensity_compliance": "high"},\n'
            '  "strain_assessment": {"fatigue_level": "moderate", "recovery_recommendation": "Active recovery tomorrow"},\n'
            '  "recommendations": ["Recommendation 1", "Recommendation 2"]\n'
            "}"
        )

    @staticmethod
    def build_planning_system_prompt(
        philosophy: CoachingPhilosophy,
        horizon_days: int,
        available_days_per_week: int,
    ) -> str:
        custom_notes = (
            f"\nATHLETE MANUAL CONSTRAINTS & METHODOLOGY NOTES:\n{philosophy.custom_context_notes}\n"
            if philosophy.custom_context_notes
            else ""
        )

        return (
            "You are an expert exercise physiologist, strength coach, and periodization specialist.\n"
            f"Synthesize an adaptive {horizon_days}-day training microcycle tailored to the athlete's target goal.\n\n"
            "ACTIVE COACHING PHILOSOPHY & CONSTRAINTS:\n"
            f"- Name: {philosophy.name}\n"
            f"- Primary Modality: {philosophy.primary_modality}\n"
            f"- Target Zone 2 (Aerobic Base) Volume: {float(philosophy.target_zone2_pct)}%\n"
            f"- Max Weekly Volume Ramp Limit: {float(philosophy.max_weekly_volume_ramp_pct)}%\n"
            f"- Max RPE Threshold: {float(philosophy.max_rpe_threshold)}\n"
            f"- Minimum Rest Days Per Week: {philosophy.min_rest_days_per_week}\n"
            f"- Available Training Days: {available_days_per_week} days per 7-day period\n"
            f"{custom_notes}\n"
            "PERIODIZATION PRINCIPLES:\n"
            f"1. Generate exactly {horizon_days} day entries (day_offset 0 to {horizon_days - 1}).\n"
            f"2. Ensure at least {philosophy.min_rest_days_per_week} rest days per 7-day period (discipline 'rest').\n"
            f"3. Volume Ramp: Planned weekly duration/volume must not exceed baseline historical volume by more than {float(philosophy.max_weekly_volume_ramp_pct)}%.\n"
            "4. Allowed disciplines: 'outdoor_run', 'indoor_row', 'erg_bike', 'strength', 'rest'.\n"
            "5. For strength sessions, provide structured exercises with sets, reps, and target RPE.\n"
            "6. Strictly honor all athlete manual constraints, injury precautions, and movement preferences.\n\n"
            "OUTPUT FORMAT RULES:\n"
            "You MUST respond ONLY with a valid JSON object matching this exact schema (no prose outside JSON):\n"
            "{\n"
            '  "summary_markdown": "### Microcycle Strategic Overview\\n\\nExplanation of progressive overload and recovery...",\n'
            '  "workouts": [\n'
            "    {\n"
            '      "day_offset": 0,\n'
            '      "discipline": "outdoor_run",\n'
            '      "title": "Zone 2 Base Aerobic Run",\n'
            '      "planned_duration_min": 45,\n'
            '      "target_distance_m": 7000.0,\n'
            '      "target_zone": "Zone 2",\n'
            '      "target_rpe": 5.0,\n'
            '      "strength_exercises": null,\n'
            '      "notes": "Keep heart rate under Zone 2 ceiling."\n'
            "    }\n"
            "  ]\n"
            "}"
        )

    async def get_active_philosophy(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> CoachingPhilosophy:
        stmt = (
            select(CoachingPhilosophy)
            .where(
                and_(
                    CoachingPhilosophy.user_id == user_id,
                    CoachingPhilosophy.is_active.is_(True),
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        philosophy = result.scalar_one_or_none()
        if philosophy:
            return philosophy

        # Fallback to any philosophy for user
        stmt_fallback = (
            select(CoachingPhilosophy)
            .where(CoachingPhilosophy.user_id == user_id)
            .order_by(CoachingPhilosophy.created_at.asc())
            .limit(1)
        )
        res_fb = await session.execute(stmt_fallback)
        philosophy = res_fb.scalar_one_or_none()
        if philosophy:
            philosophy.is_active = True
            await session.commit()
            return philosophy

        # Create default Polarized 80/20 philosophy
        default_phil = CoachingPhilosophy(
            id=uuid.uuid4(),
            user_id=user_id,
            name="Polarized 80/20",
            description="80% low-intensity Zone 2 aerobic volume, 20% high-intensity interval / strength work.",
            target_zone2_pct=80.0,
            max_weekly_volume_ramp_pct=10.0,
            max_rpe_threshold=8.5,
            min_rest_days_per_week=2,
            primary_modality="hybrid",
            is_active=True,
        )
        session.add(default_phil)
        await session.commit()
        await session.refresh(default_phil)
        return default_phil

    async def get_active_llm_client(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> tuple[BaseLLMClient, str]:
        stmt = (
            select(LLMProviderConfig)
            .where(
                and_(
                    LLMProviderConfig.user_id == user_id,
                    LLMProviderConfig.is_active.is_(True),
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError(
                "No active LLM provider configured. Please configure and activate a provider in Coach Settings."
            )

        client = get_llm_client_for_config(
            provider_type=config.provider_type,
            endpoint_url=config.endpoint_url,
            api_key_encrypted=config.api_key_encrypted,
            model_name=config.model_name,
            temperature=float(config.temperature),
            max_tokens=config.max_tokens,
        )
        return client, config.provider_type

    async def analyze_workout(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        workout_session_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        philosophy: Optional[CoachingPhilosophy] = None,
        llm_client: Optional[BaseLLMClient] = None,
        provider_name: Optional[str] = None,
    ) -> CoachingCritique:
        """Evaluates workout session(s) against active philosophy and saves a CoachingCritique."""
        if not philosophy:
            philosophy = await self.get_active_philosophy(session, user_id)

        if not llm_client:
            llm_client, provider_name = await self.get_active_llm_client(session, user_id)
        elif not provider_name:
            provider_name = "custom"

        # 1. Fetch workout session(s)
        workouts: List[WorkoutSession] = []
        if workout_session_id:
            stmt = select(WorkoutSession).where(
                and_(
                    WorkoutSession.id == workout_session_id,
                    WorkoutSession.user_id == user_id,
                )
            )
            res = await session.execute(stmt)
            ws = res.scalar_one_or_none()
            if ws:
                workouts.append(ws)
        elif start_date or end_date:
            conditions = [WorkoutSession.user_id == user_id]
            if start_date:
                conditions.append(WorkoutSession.start_time_utc >= start_date)
            if end_date:
                conditions.append(WorkoutSession.start_time_utc <= end_date)
            stmt = (
                select(WorkoutSession)
                .where(and_(*conditions))
                .order_by(WorkoutSession.start_time_utc.asc())
            )
            res = await session.execute(stmt)
            workouts = list(res.scalars().all())
        else:
            # Most recent workout session
            stmt = (
                select(WorkoutSession)
                .where(WorkoutSession.user_id == user_id)
                .order_by(WorkoutSession.start_time_utc.desc())
                .limit(1)
            )
            res = await session.execute(stmt)
            ws = res.scalar_one_or_none()
            if ws:
                workouts.append(ws)

        if not workouts:
            raise ValueError("No workout sessions found for the specified criteria.")

        # 2. Fetch associated strength sets if any
        session_ids = [w.id for w in workouts]
        strength_sets: List[Dict[str, Any]] = []
        if session_ids:
            stmt_sets = (
                select(StrengthSet, StrengthExercise.canonical_name)
                .join(StrengthExercise, StrengthSet.exercise_id == StrengthExercise.id)
                .where(StrengthSet.workout_session_id.in_(session_ids))
                .order_by(StrengthSet.set_index.asc())
            )
            res_sets = await session.execute(stmt_sets)
            for s_set, ex_name in res_sets.all():
                strength_sets.append({
                    "exercise_name": ex_name,
                    "set_index": s_set.set_index,
                    "reps_completed": s_set.reps_completed,
                    "weight": float(s_set.weight) if s_set.weight is not None else None,
                    "weight_unit": s_set.weight_unit,
                    "is_bodyweight": s_set.is_bodyweight,
                    "added_weight": float(s_set.added_weight) if s_set.added_weight is not None else None,
                    "rpe": float(s_set.rpe) if s_set.rpe is not None else None,
                    "is_warmup": s_set.is_warmup,
                })

        # 3. Build scrubbed telemetry context (Constitution Principle I)
        raw_workout_dicts = []
        for w in workouts:
            raw_workout_dicts.append({
                "discipline": w.discipline,
                "title": w.title,
                "start_time_utc": w.start_time_utc.isoformat() if w.start_time_utc else None,
                "total_duration_sec": w.total_duration_sec,
                "active_duration_sec": w.active_duration_sec,
                "total_distance_m": float(w.total_distance_m) if w.total_distance_m is not None else None,
                "total_calories": w.total_calories,
                "avg_heart_rate": w.avg_heart_rate,
                "max_heart_rate": w.max_heart_rate,
                "zone1_duration_sec": w.zone1_duration_sec,
                "zone2_duration_sec": w.zone2_duration_sec,
                "zone3_duration_sec": w.zone3_duration_sec,
                "zone4_duration_sec": w.zone4_duration_sec,
                "zone5_duration_sec": w.zone5_duration_sec,
                "avg_pace_sec_per_km": w.avg_pace_sec_per_km,
                "avg_power_watts": w.avg_power_watts,
                "avg_split_sec_per_500m": w.avg_split_sec_per_500m,
                "user_notes": w.user_notes,
            })

        scrubbed_context = PrivacyScrubberService.scrub_coaching_context(
            athlete_context={},
            recent_workouts=raw_workout_dicts,
            recent_strength_sets=strength_sets,
            philosophy={
                "name": philosophy.name,
                "target_zone2_pct": float(philosophy.target_zone2_pct),
                "max_weekly_volume_ramp_pct": float(philosophy.max_weekly_volume_ramp_pct),
            },
        )

        # 4. Generate structured critique via LLM
        system_prompt = self.build_analysis_system_prompt(philosophy)
        user_prompt = f"ATHLETIC TELEMETRY PAYLOAD:\n{json.dumps(scrubbed_context, indent=2)}"

        raw_response = await llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        parsed = self.parse_critique_response(raw_response)

        # 5. Persist critique
        critique = CoachingCritique(
            id=uuid.uuid4(),
            user_id=user_id,
            workout_session_id=workouts[0].id if len(workouts) == 1 else None,
            start_date=workouts[0].start_time_utc if workouts else None,
            end_date=workouts[-1].start_time_utc if workouts else None,
            philosophy_id=philosophy.id,
            provider_used=provider_name,
            adherence_score=parsed.adherence_score,
            summary_markdown=parsed.summary_markdown,
            adherence_details=parsed.adherence_details,
            strain_assessment=parsed.strain_assessment,
            recommendations=parsed.recommendations,
        )
        session.add(critique)
        await session.commit()
        await session.refresh(critique)

        return critique

    async def generate_forward_plan(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        target_goal: str,
        horizon_days: int = 7,
        available_days_per_week: int = 4,
        philosophy: Optional[CoachingPhilosophy] = None,
        llm_client: Optional[BaseLLMClient] = None,
        provider_name: Optional[str] = None,
    ) -> TrainingSchedulePlan:
        """Synthesizes periodized forward microcycle plan and discrete ScheduledWorkout entities."""
        if not philosophy:
            philosophy = await self.get_active_philosophy(session, user_id)

        if not llm_client:
            llm_client, provider_name = await self.get_active_llm_client(session, user_id)
        elif not provider_name:
            provider_name = "custom"

        # 1. Fetch recent 28 days of workout history to establish baseline volume
        now = datetime.now(timezone.utc)
        since_date = now - timedelta(days=28)
        stmt = (
            select(WorkoutSession)
            .where(
                and_(
                    WorkoutSession.user_id == user_id,
                    WorkoutSession.start_time_utc >= since_date,
                )
            )
            .order_by(WorkoutSession.start_time_utc.desc())
        )
        res = await session.execute(stmt)
        recent_workouts = list(res.scalars().all())

        total_recent_sec = sum(w.total_duration_sec or 0 for w in recent_workouts)
        avg_weekly_duration_min = round((total_recent_sec / 4.0) / 60.0, 1)

        history_summary = {
            "historical_window_days": 28,
            "total_workouts_completed": len(recent_workouts),
            "baseline_avg_weekly_duration_min": avg_weekly_duration_min,
            "recent_disciplines": list(set(w.discipline for w in recent_workouts)),
        }

        # 2. Build prompts
        system_prompt = self.build_planning_system_prompt(
            philosophy=philosophy,
            horizon_days=horizon_days,
            available_days_per_week=available_days_per_week,
        )

        user_prompt = (
            f"TARGET GOAL: {target_goal}\n"
            f"HORIZON DAYS: {horizon_days}\n"
            f"AVAILABLE TRAINING DAYS PER WEEK: {available_days_per_week}\n"
            f"BASELINE HISTORICAL VOLUME:\n{json.dumps(history_summary, indent=2)}"
        )

        # 3. LLM Generation
        raw_response = await llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        parsed = self.parse_schedule_response(raw_response)

        # 4. Compute microcycle date boundaries
        today = date.today()
        start_date = today
        end_date = today + timedelta(days=horizon_days - 1)

        # 5. Supersede any existing active plans for this user
        stmt_supersede = (
            update(TrainingSchedulePlan)
            .where(
                and_(
                    TrainingSchedulePlan.user_id == user_id,
                    TrainingSchedulePlan.status == "active",
                )
            )
            .values(status="superseded")
        )
        await session.execute(stmt_supersede)

        # 6. Save new plan
        plan = TrainingSchedulePlan(
            id=uuid.uuid4(),
            user_id=user_id,
            philosophy_id=philosophy.id,
            target_goal=target_goal,
            start_date=start_date,
            end_date=end_date,
            horizon_days=horizon_days,
            summary_markdown=parsed.summary_markdown,
            status="active",
        )
        session.add(plan)
        await session.flush()

        # 7. Create ScheduledWorkout items
        for item in parsed.workouts:
            workout_date = start_date + timedelta(days=item.day_offset)
            scheduled = ScheduledWorkout(
                id=uuid.uuid4(),
                plan_id=plan.id,
                target_date=workout_date,
                discipline=item.discipline,
                title=item.title,
                planned_duration_min=item.planned_duration_min,
                target_distance_m=item.target_distance_m,
                target_zone=item.target_zone,
                target_rpe=item.target_rpe,
                strength_exercises=item.strength_exercises,
                notes=item.notes,
                is_completed=False,
            )
            session.add(scheduled)

        await session.commit()

        # Refresh plan with scheduled workouts loaded
        stmt_load = (
            select(TrainingSchedulePlan)
            .options(selectinload(TrainingSchedulePlan.scheduled_workouts))
            .where(TrainingSchedulePlan.id == plan.id)
        )
        res_load = await session.execute(stmt_load)
        return res_load.scalar_one()

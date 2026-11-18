"""Personal Record (PR) detection and peak performance calculation engine."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.exercise import StrengthExercise
from src.models.strength_set import StrengthSet
from src.models.workout import WorkoutSession
from src.schemas.analytics import PersonalRecordItem, WindowPreset
from src.services.analytics_service import AnalyticsService

KG_TO_LBS = 2.20462


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class PRDetectorService:
    def __init__(self):
        self.analytics_service = AnalyticsService()

    @staticmethod
    def calculate_epley_1rm(weight: float, reps: int) -> Optional[float]:
        """Calculates estimated 1RM using the standard Epley formula w * (1 + r / 30).
        
        Strictly capped at sets of 10 or fewer reps. Sets > 10 reps are muscular endurance.
        """
        if reps <= 0 or weight <= 0:
            return 0.0
        if reps > 10:
            return None
        if reps == 1:
            return round(float(weight), 2)
        return round(float(weight) * (1.0 + float(reps) / 30.0), 2)

    @staticmethod
    def calculate_estimated_5rm(estimated_1rm: Optional[float]) -> Optional[float]:
        """Calculates estimated 5RM from estimated 1RM (1RM / 1.1667)."""
        if not estimated_1rm or estimated_1rm <= 0:
            return None
        return round(estimated_1rm / 1.1667, 2)

    @staticmethod
    def match_endurance_milestone(discipline: str, distance_m: float) -> Optional[str]:
        """Matches a workout distance to a benchmark milestone within +/- 3% tolerance."""
        if not distance_m or distance_m <= 0:
            return None

        # Running benchmarks (+/- 3%)
        if discipline == "outdoor_run":
            # 1 Mile = 1609.34m
            if 1609.34 * 0.97 <= distance_m <= 1609.34 * 1.03:
                return "1_mile"
            # 5k = 5000m
            if 5000.0 * 0.97 <= distance_m <= 5000.0 * 1.03:
                return "5k"
            # 10k = 10000m
            if 10000.0 * 0.97 <= distance_m <= 10000.0 * 1.03:
                return "10k"

        # Concept2 indoor row benchmarks (+/- 3%)
        elif discipline == "indoor_row":
            if 500.0 * 0.97 <= distance_m <= 500.0 * 1.03:
                return "500m_erg"
            if 2000.0 * 0.97 <= distance_m <= 2000.0 * 1.03:
                return "2k_erg"
            if 5000.0 * 0.97 <= distance_m <= 5000.0 * 1.03:
                return "5k_erg"

        # Concept2 bike erg benchmarks (+/- 3%)
        elif discipline == "erg_bike":
            if 2000.0 * 0.97 <= distance_m <= 2000.0 * 1.03:
                return "2k_erg"
            if 5000.0 * 0.97 <= distance_m <= 5000.0 * 1.03:
                return "5k_erg"

        return None

    @staticmethod
    def format_time_mmss(seconds: float) -> str:
        """Formats seconds into MM:SS or HH:MM:SS."""
        secs = int(seconds)
        mins, s = divmod(secs, 60)
        hours, m = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    async def get_all_prs(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        window: Optional[WindowPreset] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[PersonalRecordItem]:
        """Scans training history and returns personal records."""
        if start_time and end_time:
            window_start, window_end = start_time, end_time
        else:
            window_start, window_end = self.analytics_service.resolve_date_window(
                window or WindowPreset.ALL_TIME
            )

        prs: List[PersonalRecordItem] = []

        # --- 1. Strength PRs ---
        stmt_strength = (
            select(StrengthSet, StrengthExercise, WorkoutSession.start_time_utc)
            .join(WorkoutSession, StrengthSet.workout_session_id == WorkoutSession.id)
            .join(StrengthExercise, StrengthSet.exercise_id == StrengthExercise.id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.status == "active",
                StrengthSet.is_warmup.is_(False),
            )
            .order_by(StrengthSet.created_at.asc())
        )
        res_strength = await session.execute(stmt_strength)
        strength_rows = res_strength.all()

        # Track bests per exercise
        # ex_id -> { 'best_1rm': (val, date, ex_name), 'best_weight': (val, date, ex_name), 'best_reps': (val, date, ex_name) }
        exercise_bests: Dict[uuid.UUID, Dict[str, Tuple[float, datetime, str]]] = {}

        for s_set, exercise, session_date in strength_rows:
            ex_id = exercise.id
            ex_name = exercise.canonical_name
            if ex_id not in exercise_bests:
                exercise_bests[ex_id] = {}

            unit = (s_set.weight_unit or "lbs").lower()
            conv = KG_TO_LBS if unit == "kg" else 1.0

            reps = s_set.reps_completed or 0
            is_bw = s_set.is_bodyweight or exercise.is_bodyweight
            raw_wt = float(s_set.added_weight if is_bw else s_set.weight) or 0.0
            wt_lbs = raw_wt * conv

            # 1RM Calculation (reps <= 10)
            if wt_lbs > 0 and reps <= 10:
                e1rm = self.calculate_epley_1rm(wt_lbs, reps)
                if e1rm:
                    current_1rm = exercise_bests[ex_id].get("estimated_1rm_pr")
                    if current_1rm is None or e1rm > current_1rm[0]:
                        exercise_bests[ex_id]["estimated_1rm_pr"] = (e1rm, session_date, ex_name)

            # Absolute Weight PR
            if wt_lbs > 0:
                current_wt = exercise_bests[ex_id].get("weight_pr")
                if current_wt is None or wt_lbs > current_wt[0]:
                    exercise_bests[ex_id]["weight_pr"] = (wt_lbs, session_date, ex_name)

            # Pure Bodyweight Repetition PR
            if is_bw and (s_set.added_weight or 0.0) == 0.0 and reps > 0:
                current_reps = exercise_bests[ex_id].get("repetition_pr")
                if current_reps is None or reps > current_reps[0]:
                    exercise_bests[ex_id]["repetition_pr"] = (float(reps), session_date, ex_name)

        for ex_id, bests in exercise_bests.items():
            for m_type, (val, raw_achieved_at, ex_name) in bests.items():
                achieved_at = ensure_utc(raw_achieved_at)
                is_recent = (achieved_at >= window_start) if window_start and achieved_at else True
                if m_type == "estimated_1rm_pr":
                    prs.append(
                        PersonalRecordItem(
                            discipline="strength",
                            title=f"{ex_name} Estimated 1RM",
                            exercise_name=ex_name,
                            milestone_type="estimated_1rm_pr",
                            record_display=f"{val:.1f} lbs",
                            record_value=val,
                            record_unit="lbs",
                            estimated_1rm=val,
                            achieved_at=achieved_at,
                            is_recent=is_recent,
                        )
                    )
                elif m_type == "weight_pr":
                    prs.append(
                        PersonalRecordItem(
                            discipline="strength",
                            title=f"{ex_name} Max Weight",
                            exercise_name=ex_name,
                            milestone_type="weight_pr",
                            record_display=f"{val:.1f} lbs",
                            record_value=val,
                            record_unit="lbs",
                            estimated_1rm=None,
                            achieved_at=achieved_at,
                            is_recent=is_recent,
                        )
                    )
                elif m_type == "repetition_pr":
                    prs.append(
                        PersonalRecordItem(
                            discipline="strength",
                            title=f"{ex_name} Max Reps",
                            exercise_name=ex_name,
                            milestone_type="repetition_pr",
                            record_display=f"{int(val)} reps",
                            record_value=val,
                            record_unit="reps",
                            estimated_1rm=None,
                            achieved_at=achieved_at,
                            is_recent=is_recent,
                        )
                    )

        # --- 2. Cardio Milestone PRs ---
        stmt_cardio = (
            select(WorkoutSession)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.status == "active",
                WorkoutSession.discipline.in_(["outdoor_run", "indoor_row", "erg_bike"]),
            )
            .order_by(WorkoutSession.start_time_utc.asc())
        )
        res_cardio = await session.execute(stmt_cardio)
        cardio_sessions = res_cardio.scalars().all()

        cardio_bests: Dict[Tuple[str, str], Tuple[float, datetime, WorkoutSession]] = {}

        for w in cardio_sessions:
            dist = w.total_distance_m or 0.0
            milestone = self.match_endurance_milestone(w.discipline, dist)
            if not milestone:
                continue

            dur = w.active_duration_sec or w.total_duration_sec or 0.0
            if dur <= 0:
                continue

            key = (w.discipline, milestone)
            current_best = cardio_bests.get(key)
            if current_best is None or dur < current_best[0]:
                cardio_bests[key] = (dur, w.start_time_utc, w)

        milestone_titles = {
            "1_mile": "1 Mile Run",
            "5k": "5k Run",
            "10k": "10k Run",
            "500m_erg": "500m Erg Row",
            "2k_erg": "2k Erg",
            "5k_erg": "5k Erg",
        }

        for (disc, milestone), (dur, raw_achieved_at, w) in cardio_bests.items():
            achieved_at = ensure_utc(raw_achieved_at)
            is_recent = (achieved_at >= window_start) if window_start and achieved_at else True
            title = milestone_titles.get(milestone, f"{disc} {milestone}")
            time_display = self.format_time_mmss(dur)

            extra = ""
            if disc == "outdoor_run" and w.avg_pace_sec_per_km:
                pace_str = self.format_time_mmss(w.avg_pace_sec_per_km)
                extra = f" ({pace_str}/km)"
            elif "row" in disc and w.avg_split_sec_per_500m:
                split_str = self.format_time_mmss(w.avg_split_sec_per_500m)
                extra = f" ({split_str}/500m)"

            prs.append(
                PersonalRecordItem(
                    discipline=disc,
                    title=title,
                    exercise_name=None,
                    milestone_type=milestone,
                    record_display=f"{time_display}{extra}",
                    record_value=round(dur, 2),
                    record_unit="sec",
                    estimated_1rm=None,
                    achieved_at=achieved_at,
                    is_recent=is_recent,
                )
            )

        prs.sort(key=lambda p: (not p.is_recent, p.discipline, p.title))
        return prs

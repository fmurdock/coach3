"""Analytics service for unified training volume and cardio metrics."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import WorkoutSession
from src.schemas.analytics import (
    CardioAnalyticsResponse,
    CardioWeeklyTrendPoint,
    StrengthAnalyticsResponse,
    UnifiedVolumeSummary,
    WindowPreset,
)

KM_TO_MILES = 0.621371


KG_TO_LBS = 2.20462


class AnalyticsService:
    @staticmethod
    def resolve_date_window(
        window: Optional[WindowPreset] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Tuple[datetime, datetime]:
        """Resolves date bounds to UTC datetimes."""
        now = datetime.now(timezone.utc)
        if start_date and end_date:
            start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
            return start_dt, end_dt

        preset = window or WindowPreset.THIRTY_DAYS
        if preset == WindowPreset.SEVEN_DAYS:
            return now - timedelta(days=7), now
        elif preset == WindowPreset.THIRTY_DAYS:
            return now - timedelta(days=30), now
        elif preset == WindowPreset.NINETY_DAYS:
            return now - timedelta(days=90), now
        elif preset == WindowPreset.YEAR_TO_DATE:
            return datetime(now.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc), now
        elif preset == WindowPreset.ALL_TIME:
            return datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc), now
        return now - timedelta(days=30), now

    async def get_cardio_metrics(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> CardioAnalyticsResponse:
        """Aggregates cardiovascular volume, Zone 2 duration, and weekly trends."""
        stmt = (
            select(WorkoutSession)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.start_time_utc >= start_time,
                WorkoutSession.start_time_utc <= end_time,
                WorkoutSession.discipline.in_(["outdoor_run", "indoor_row", "erg_bike"]),
                WorkoutSession.status == "active",
            )
            .order_by(WorkoutSession.start_time_utc.asc())
        )
        result = await session.execute(stmt)
        workouts = result.scalars().all()

        total_distance_m = 0.0
        total_duration_sec = 0.0
        zone1_sec = 0.0
        zone2_sec = 0.0
        zone3_sec = 0.0
        zone4_sec = 0.0
        zone5_sec = 0.0
        outdoor_run_m = 0.0
        erg_row_m = 0.0
        erg_bike_m = 0.0

        weekly_buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"miles": 0.0, "zone2_hours": 0.0}
        )

        for w in workouts:
            dist = w.total_distance_m or 0.0
            dur = w.total_duration_sec or 0.0
            z1 = w.zone1_duration_sec or 0.0
            z2 = w.zone2_duration_sec or 0.0
            z3 = w.zone3_duration_sec or 0.0
            z4 = w.zone4_duration_sec or 0.0
            z5 = w.zone5_duration_sec or 0.0

            total_distance_m += dist
            total_duration_sec += dur
            zone1_sec += z1
            zone2_sec += z2
            zone3_sec += z3
            zone4_sec += z4
            zone5_sec += z5

            if w.discipline == "outdoor_run":
                outdoor_run_m += dist
            elif w.discipline == "indoor_row":
                erg_row_m += dist
            elif w.discipline == "erg_bike":
                erg_bike_m += dist

            # Weekly bucket by ISO week label (e.g., 'W46 (11/11)')
            start_date_val = w.start_time_utc.date()
            monday = start_date_val - timedelta(days=start_date_val.weekday())
            week_label = f"W{monday.isocalendar()[1]} ({monday.strftime('%m/%d')})"
            miles = (dist / 1000.0) * KM_TO_MILES
            weekly_buckets[week_label]["miles"] += miles
            weekly_buckets[week_label]["zone2_hours"] += z2 / 3600.0

        total_distance_km = round(total_distance_m / 1000.0, 2)
        total_distance_miles = round(total_distance_km * KM_TO_MILES, 2)
        total_duration_hours = round(total_duration_sec / 3600.0, 2)
        zone2_duration_hours = round(zone2_sec / 3600.0, 2)
        zone2_percentage = (
            round((zone2_sec / total_duration_sec) * 100.0, 1)
            if total_duration_sec > 0
            else 0.0
        )

        zone_dist = {
            "zone1": round(zone1_sec / 3600.0, 2),
            "zone2": zone2_duration_hours,
            "zone3": round(zone3_sec / 3600.0, 2),
            "zone4": round(zone4_sec / 3600.0, 2),
            "zone5": round(zone5_sec / 3600.0, 2),
        }

        weekly_trend = [
            CardioWeeklyTrendPoint(
                week_label=label,
                miles=round(data["miles"], 2),
                zone2_hours=round(data["zone2_hours"], 2),
            )
            for label, data in sorted(weekly_buckets.items())
        ]

        return CardioAnalyticsResponse(
            total_distance_km=total_distance_km,
            total_distance_miles=total_distance_miles,
            total_duration_hours=total_duration_hours,
            zone2_duration_hours=zone2_duration_hours,
            zone2_percentage=zone2_percentage,
            zone_distribution_hours=zone_dist,
            weekly_trend=weekly_trend,
            outdoor_run_km=round(outdoor_run_m / 1000.0, 2),
            erg_row_meters=round(erg_row_m, 2),
            erg_bike_meters=round(erg_bike_m, 2),
        )

    async def get_strength_metrics(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> StrengthAnalyticsResponse:
        """Aggregates strength volume load, effective sets, and muscle groups."""
        from src.models.exercise import StrengthExercise
        from src.models.strength_set import StrengthSet

        stmt = (
            select(StrengthSet, StrengthExercise)
            .join(WorkoutSession, StrengthSet.workout_session_id == WorkoutSession.id)
            .join(StrengthExercise, StrengthSet.exercise_id == StrengthExercise.id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.start_time_utc >= start_time,
                WorkoutSession.start_time_utc <= end_time,
                WorkoutSession.status == "active",
            )
            .order_by(StrengthSet.created_at.asc())
        )
        result = await session.execute(stmt)
        rows = result.all()

        total_volume_load_lbs = 0.0
        effective_working_sets = 0
        total_reps = 0
        added_calisthenic_load_lbs = 0.0
        muscle_group_sets: Dict[str, int] = defaultdict(int)
        muscle_group_volume: Dict[str, float] = defaultdict(float)

        for s_set, exercise in rows:
            if s_set.is_warmup:
                continue

            unit = (s_set.weight_unit or "lbs").lower()
            conv = KG_TO_LBS if unit == "kg" else 1.0

            reps = s_set.reps_completed or 0
            is_bw = s_set.is_bodyweight or exercise.is_bodyweight

            if is_bw:
                added_wt = (float(s_set.added_weight) if s_set.added_weight is not None else 0.0) * conv
                set_vol = added_wt * reps
                added_calisthenic_load_lbs += set_vol
            else:
                wt = (float(s_set.weight) if s_set.weight is not None else 0.0) * conv
                set_vol = wt * reps

            total_volume_load_lbs += set_vol
            effective_working_sets += 1
            total_reps += reps

            mg = (exercise.primary_muscle_group or "full body").lower()
            muscle_group_sets[mg] += 1
            muscle_group_volume[mg] += set_vol

        return StrengthAnalyticsResponse(
            total_volume_load_lbs=round(total_volume_load_lbs, 2),
            effective_working_sets=effective_working_sets,
            total_reps=total_reps,
            muscle_group_sets=dict(muscle_group_sets),
            muscle_group_volume={k: round(v, 2) for k, v in muscle_group_volume.items()},
            added_calisthenic_load_lbs=round(added_calisthenic_load_lbs, 2),
        )

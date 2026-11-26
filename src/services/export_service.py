"""Lossless training history export service producing a single ZIP archive (backup.json + CSV summaries)."""

import csv
from datetime import datetime, timezone
import io
import json
from typing import Any
import zipfile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.coaching import CoachingCritique, CoachingPhilosophy, TrainingSchedulePlan
from src.models.exercise import StrengthExercise
from src.models.strength_set import StrengthSet
from src.models.user import User, UserHeartRateProfile
from src.models.workout import WorkoutSession


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _num(val: Any) -> float | None:
    if val is None:
        return None
    return float(val)


class ExportService:
    @classmethod
    async def build_export_zip(
        cls,
        db: AsyncSession,
        user: User,
        include_demo: bool = False,
    ) -> bytes:
        """Assemble a lossless backup ZIP (backup.json + workouts.csv + strength_sets.csv).

        Strictly excludes all encrypted secrets, API keys, OAuth tokens, and passphrase hashes.
        Excludes synthetic demo workouts (is_demo=True) by default.
        """
        # 1. HR Profile
        hr_res = await db.execute(
            select(UserHeartRateProfile).where(UserHeartRateProfile.user_id == user.id)
        )
        hr_profile = hr_res.scalar_one_or_none()
        hr_profile_dict = (
            {
                "resting_hr": hr_profile.resting_hr,
                "max_hr": hr_profile.max_hr,
                "zone1_min": hr_profile.zone1_min,
                "zone1_max": hr_profile.zone1_max,
                "zone2_min": hr_profile.zone2_min,
                "zone2_max": hr_profile.zone2_max,
                "zone3_min": hr_profile.zone3_min,
                "zone3_max": hr_profile.zone3_max,
                "zone4_min": hr_profile.zone4_min,
                "zone4_max": hr_profile.zone4_max,
                "zone5_min": hr_profile.zone5_min,
                "zone5_max": hr_profile.zone5_max,
            }
            if hr_profile
            else None
        )

        # 2. Exercises catalog
        ex_res = await db.execute(
            select(StrengthExercise).options(selectinload(StrengthExercise.aliases))
        )
        exercises = ex_res.scalars().all()
        exercises_list = [
            {
                "id": str(ex.id),
                "canonical_name": ex.canonical_name,
                "slug": ex.slug,
                "category": ex.category,
                "primary_muscle_group": ex.primary_muscle_group,
                "is_bodyweight": ex.is_bodyweight,
                "default_unit": ex.default_unit,
                "aliases": [a.alias for a in ex.aliases],
            }
            for ex in exercises
        ]

        # 3. Workouts with full lossless telemetry & strength sets
        w_stmt = (
            select(WorkoutSession)
            .options(
                selectinload(WorkoutSession.heart_rate_samples),
                selectinload(WorkoutSession.gps_route_points),
                selectinload(WorkoutSession.splits),
                selectinload(WorkoutSession.strength_sets).selectinload(StrengthSet.exercise),
            )
            .where(WorkoutSession.user_id == user.id)
            .order_by(WorkoutSession.start_time_utc.asc())
        )
        if not include_demo:
            w_stmt = w_stmt.where(WorkoutSession.is_demo.is_(False))

        workouts = (await db.execute(w_stmt)).scalars().all()

        workouts_json: list[dict[str, Any]] = []
        workouts_csv_rows: list[dict[str, Any]] = []
        strength_csv_rows: list[dict[str, Any]] = []

        for w in workouts:
            sorted_hr = sorted(w.heart_rate_samples, key=lambda x: x.elapsed_sec)
            sorted_gps = sorted(w.gps_route_points, key=lambda x: x.elapsed_sec)
            sorted_splits = sorted(w.splits, key=lambda x: x.split_index)
            sorted_sets = sorted(w.strength_sets, key=lambda x: x.set_index)

            workouts_json.append(
                {
                    "id": str(w.id),
                    "provider": w.provider,
                    "external_id": w.external_id,
                    "discipline": w.discipline,
                    "title": w.title,
                    "start_time_utc": _iso(w.start_time_utc),
                    "local_timezone": w.local_timezone,
                    "total_duration_sec": w.total_duration_sec,
                    "active_duration_sec": w.active_duration_sec,
                    "total_distance_m": w.total_distance_m,
                    "total_calories": w.total_calories,
                    "avg_heart_rate": w.avg_heart_rate,
                    "max_heart_rate": w.max_heart_rate,
                    "zone1_duration_sec": w.zone1_duration_sec,
                    "zone2_duration_sec": w.zone2_duration_sec,
                    "zone3_duration_sec": w.zone3_duration_sec,
                    "zone4_duration_sec": w.zone4_duration_sec,
                    "zone5_duration_sec": w.zone5_duration_sec,
                    "avg_pace_sec_per_km": w.avg_pace_sec_per_km,
                    "elevation_gain_m": w.elevation_gain_m,
                    "elevation_loss_m": w.elevation_loss_m,
                    "total_strokes": w.total_strokes,
                    "avg_cadence_spm": w.avg_cadence_spm,
                    "avg_power_watts": w.avg_power_watts,
                    "avg_split_sec_per_500m": w.avg_split_sec_per_500m,
                    "avg_drag_factor": w.avg_drag_factor,
                    "user_notes": w.user_notes,
                    "is_demo": w.is_demo,
                    "status": w.status,
                    "heart_rate_samples": [
                        {
                            "elapsed_sec": s.elapsed_sec,
                            "bpm": s.bpm,
                            "timestamp_utc": _iso(s.timestamp_utc),
                        }
                        for s in sorted_hr
                    ],
                    "gps_route_points": [
                        {
                            "elapsed_sec": p.elapsed_sec,
                            "latitude": p.latitude,
                            "longitude": p.longitude,
                            "altitude_m": p.altitude_m,
                            "timestamp_utc": _iso(p.timestamp_utc),
                        }
                        for p in sorted_gps
                    ],
                    "splits": [
                        {
                            "split_index": sp.split_index,
                            "split_type": sp.split_type,
                            "distance_m": sp.distance_m,
                            "duration_sec": sp.duration_sec,
                            "avg_pace_sec_per_km": sp.avg_pace_sec_per_km,
                            "avg_power_watts": sp.avg_power_watts,
                            "avg_cadence_spm": sp.avg_cadence_spm,
                            "avg_heart_rate": sp.avg_heart_rate,
                            "avg_split_sec_per_500m": sp.avg_split_sec_per_500m,
                        }
                        for sp in sorted_splits
                    ],
                    "strength_sets": [
                        {
                            "id": str(s.id),
                            "exercise_id": str(s.exercise_id),
                            "exercise_name": s.exercise.canonical_name if s.exercise else None,
                            "set_index": s.set_index,
                            "reps_completed": s.reps_completed,
                            "target_reps": s.target_reps,
                            "weight": _num(s.weight),
                            "weight_unit": s.weight_unit,
                            "is_bodyweight": s.is_bodyweight,
                            "added_weight": _num(s.added_weight),
                            "rpe": _num(s.rpe),
                            "is_warmup": s.is_warmup,
                            "rest_seconds": s.rest_seconds,
                            "completed_at": _iso(s.completed_at),
                        }
                        for s in sorted_sets
                    ],
                }
            )

            workouts_csv_rows.append(
                {
                    "workout_id": str(w.id),
                    "start_time_utc": _iso(w.start_time_utc),
                    "provider": w.provider,
                    "discipline": w.discipline,
                    "title": w.title,
                    "total_duration_sec": w.total_duration_sec,
                    "total_distance_m": w.total_distance_m,
                    "total_calories": w.total_calories,
                    "avg_heart_rate": w.avg_heart_rate,
                    "max_heart_rate": w.max_heart_rate,
                    "zone1_sec": w.zone1_duration_sec,
                    "zone2_sec": w.zone2_duration_sec,
                    "zone3_sec": w.zone3_duration_sec,
                    "zone4_sec": w.zone4_duration_sec,
                    "zone5_sec": w.zone5_duration_sec,
                    "avg_pace_sec_per_km": w.avg_pace_sec_per_km,
                    "avg_split_sec_per_500m": w.avg_split_sec_per_500m,
                    "avg_power_watts": w.avg_power_watts,
                    "user_notes": w.user_notes or "",
                }
            )

            for s in sorted_sets:
                strength_csv_rows.append(
                    {
                        "workout_id": str(w.id),
                        "workout_date_utc": _iso(w.start_time_utc),
                        "set_id": str(s.id),
                        "set_index": s.set_index,
                        "exercise_name": s.exercise.canonical_name if s.exercise else "",
                        "muscle_group": s.exercise.primary_muscle_group if s.exercise else "",
                        "reps_completed": s.reps_completed,
                        "weight": _num(s.weight),
                        "weight_unit": s.weight_unit,
                        "is_bodyweight": s.is_bodyweight,
                        "added_weight": _num(s.added_weight),
                        "rpe": _num(s.rpe),
                        "is_warmup": s.is_warmup,
                        "rest_seconds": s.rest_seconds,
                        "completed_at": _iso(s.completed_at),
                    }
                )

        # 4. Coaching Philosophies, Critiques, and Training Plans (zero LLM provider secrets!)
        phils = (
            await db.execute(
                select(CoachingPhilosophy)
                .where(CoachingPhilosophy.user_id == user.id)
                .order_by(CoachingPhilosophy.created_at.asc())
            )
        ).scalars().all()
        critiques = (
            await db.execute(
                select(CoachingCritique)
                .where(CoachingCritique.user_id == user.id)
                .order_by(CoachingCritique.created_at.asc())
            )
        ).scalars().all()
        plans = (
            await db.execute(
                select(TrainingSchedulePlan)
                .options(selectinload(TrainingSchedulePlan.scheduled_workouts))
                .where(TrainingSchedulePlan.user_id == user.id)
                .order_by(TrainingSchedulePlan.created_at.asc())
            )
        ).scalars().all()

        backup_payload = {
            "schema_version": "1.0",
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "include_demo": include_demo,
            "athlete": {
                "id": str(user.id),
                "timezone": user.timezone or "UTC",
                "hr_profile": hr_profile_dict,
            },
            "exercises": exercises_list,
            "workouts": workouts_json,
            "coaching_philosophies": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "description": p.description,
                    "target_zone2_pct": _num(p.target_zone2_pct),
                    "max_weekly_volume_ramp_pct": _num(p.max_weekly_volume_ramp_pct),
                    "max_rpe_threshold": _num(p.max_rpe_threshold),
                    "min_rest_days_per_week": p.min_rest_days_per_week,
                    "primary_modality": p.primary_modality,
                    "custom_context_notes": p.custom_context_notes,
                    "is_active": p.is_active,
                }
                for p in phils
            ],
            "coaching_critiques": [
                {
                    "id": str(c.id),
                    "workout_session_id": str(c.workout_session_id) if c.workout_session_id else None,
                    "provider_used": c.provider_used,
                    "adherence_score": _num(c.adherence_score),
                    "summary_markdown": c.summary_markdown,
                    "adherence_details": c.adherence_details,
                    "strain_assessment": c.strain_assessment,
                    "recommendations": c.recommendations,
                    "created_at": _iso(c.created_at),
                }
                for c in critiques
            ],
            "training_plans": [
                {
                    "id": str(pl.id),
                    "target_goal": pl.target_goal,
                    "start_date": _iso(pl.start_date),
                    "end_date": _iso(pl.end_date),
                    "horizon_days": pl.horizon_days,
                    "summary_markdown": pl.summary_markdown,
                    "status": pl.status,
                    "scheduled_workouts": [
                        {
                            "id": str(sw.id),
                            "target_date": _iso(sw.target_date),
                            "discipline": sw.discipline,
                            "title": sw.title,
                            "planned_duration_min": sw.planned_duration_min,
                            "target_distance_m": _num(sw.target_distance_m),
                            "target_zone": sw.target_zone,
                            "target_rpe": _num(sw.target_rpe),
                            "strength_exercises": sw.strength_exercises,
                            "notes": sw.notes,
                            "is_completed": sw.is_completed,
                        }
                        for sw in sorted(pl.scheduled_workouts, key=lambda x: x.target_date)
                    ],
                }
                for pl in plans
            ],
        }

        # 5. Pack ZIP in memory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup.json", json.dumps(backup_payload, indent=2))

            # workouts.csv
            w_csv_buf = io.StringIO()
            w_fields = [
                "workout_id",
                "start_time_utc",
                "provider",
                "discipline",
                "title",
                "total_duration_sec",
                "total_distance_m",
                "total_calories",
                "avg_heart_rate",
                "max_heart_rate",
                "zone1_sec",
                "zone2_sec",
                "zone3_sec",
                "zone4_sec",
                "zone5_sec",
                "avg_pace_sec_per_km",
                "avg_split_sec_per_500m",
                "avg_power_watts",
                "user_notes",
            ]
            w_writer = csv.DictWriter(w_csv_buf, fieldnames=w_fields)
            w_writer.writeheader()
            w_writer.writerows(workouts_csv_rows)
            zf.writestr("workouts.csv", w_csv_buf.getvalue())

            # strength_sets.csv
            s_csv_buf = io.StringIO()
            s_fields = [
                "workout_id",
                "workout_date_utc",
                "set_id",
                "set_index",
                "exercise_name",
                "muscle_group",
                "reps_completed",
                "weight",
                "weight_unit",
                "is_bodyweight",
                "added_weight",
                "rpe",
                "is_warmup",
                "rest_seconds",
                "completed_at",
            ]
            s_writer = csv.DictWriter(s_csv_buf, fieldnames=s_fields)
            s_writer.writeheader()
            s_writer.writerows(strength_csv_rows)
            zf.writestr("strength_sets.csv", s_csv_buf.getvalue())

        return zip_buf.getvalue()

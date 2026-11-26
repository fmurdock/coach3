"""Analytics service for unified training volume and cardio metrics."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import math
from typing import Any, Dict, Literal, Optional, Tuple, cast
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.concept2 import parse_concept2_strokes
from src.models import WorkoutSession
from src.schemas.workout import (
    GPSRoutePointSchema,
    IntervalConsistencyAnalysis,
    IntervalConsistencySet,
    IntervalSplitDetail,
    NormalizedSample,
    StrengthSetDetail,
    TelemetryPoint,
    WorkoutDetailTelemetry,
)
from src.schemas.analytics import (
    CardioAnalyticsResponse,
    CardioWeeklyTrendPoint,
    CardioVolumeSummary,
    DashboardMacroResponse,
    MuscleGroupVolumeSummary,
    StrengthAnalyticsResponse,
    WeeklyCardioBucket,
    WindowPreset,
)
from src.services.metrics import KG_TO_LBS, KM_TO_MILES, calculate_epley_1rm


def _resolve_tz(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo((tz_name or "UTC").strip())
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        return ZoneInfo("UTC")


def _to_local_date(dt: datetime, tz_name: str | None = "UTC") -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_resolve_tz(tz_name)).date()


class AnalyticsService:
    CANONICAL_MUSCLE_GROUPS = {
        "push": "Push",
        "pull": "Pull",
        "legs": "Legs",
        "abs": "Abs",
    }

    WEEKLY_ZONE2_GOAL_MINUTES = 120.0
    WEEKLY_VO2MAX_GOAL_MINUTES = 20.0
    WEEKLY_STRENGTH_GOAL_SETS = 10.0

    @staticmethod
    def _classify_strength_keywords(val: str) -> Optional[Tuple[str, str]]:
        if any(k in val for k in ["abs", "core", "abdominal", "oblique", "plank", "leg raise", "crunch"]):
            return "abs", "Abs"
        if any(k in val for k in ["quad", "hamstring", "glute", "calve", "calf", "leg", "squat", "deadlift", "rdl", "lunge", "hinge"]):
            return "legs", "Legs"
        if any(k in val for k in ["chest", "pec", "shoulder", "delt", "tricep", "dip", "bench", "overhead", "military", "push", "press", "skull"]):
            return "push", "Push"
        if any(k in val for k in ["back", "lat", "trap", "rhomboid", "bicep", "forearm", "row", "pull", "curl", "chin"]):
            return "pull", "Pull"
        return None

    @classmethod
    def normalize_muscle_group(
        cls,
        raw_group: Optional[str],
        exercise_name: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Maps arbitrary exercise muscle strings to Push, Pull, Legs, Abs, or fallback Other."""
        if raw_group:
            val = raw_group.lower().strip()
            if val not in ("arms", "arm", "full_body", "full body", "other", "unknown"):
                matched = cls._classify_strength_keywords(val)
                if matched:
                    return matched

        if exercise_name:
            matched_name = cls._classify_strength_keywords(exercise_name.lower().strip())
            if matched_name:
                return matched_name

        return "other", "Other"

    @staticmethod
    def calculate_estimated_1rm(weight: float, reps: int) -> Optional[float]:
        """Calculates estimated 1RM using the canonical Epley formula capped at 1 <= reps <= 10."""
        return calculate_epley_1rm(weight, reps)

    @staticmethod
    def resolve_date_window(
        window: Optional[WindowPreset] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        tz_name: str = "UTC",
    ) -> Tuple[datetime, datetime]:
        """Resolves date bounds in the athlete's local IANA timezone and returns UTC datetimes."""
        tz = _resolve_tz(tz_name)
        now = datetime.now(timezone.utc)
        if start_date and end_date:
            start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
            end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=tz).astimezone(timezone.utc)
            return start_dt, end_dt

        preset = window or WindowPreset.THIRTY_DAYS
        if preset == WindowPreset.SEVEN_DAYS:
            return now - timedelta(days=7), now
        elif preset == WindowPreset.THIRTY_DAYS:
            return now - timedelta(days=30), now
        elif preset == WindowPreset.NINETY_DAYS:
            return now - timedelta(days=90), now
        elif preset == WindowPreset.YEAR_TO_DATE:
            local_now = now.astimezone(tz)
            ytd_start = datetime(local_now.year, 1, 1, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
            return ytd_start, now
        elif preset == WindowPreset.ALL_TIME:
            return datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc), now
        return now - timedelta(days=30), now

    async def get_macro_dashboard_volume(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        tz_name: str = "UTC",
    ) -> DashboardMacroResponse:
        """Computes unified macro cardio volume (Zone 2 vs Zone 5 minutes) and muscle group sets with top weight highlights."""
        from src.models.exercise import StrengthExercise
        from src.models.strength_set import StrengthSet

        # 1. Cardio Volume Aggregation
        stmt_cardio = (
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
        res_cardio = await session.execute(stmt_cardio)
        cardio_workouts = res_cardio.scalars().all()

        total_cardio_sec = 0.0
        zone2_sec = 0.0
        zone4_sec = 0.0
        zone5_sec = 0.0

        weekly_buckets: Dict[date, Dict[str, float]] = {}

        for w in cardio_workouts:
            dur = w.total_duration_sec or 0.0
            dist = w.total_distance_m or 0.0
            z2 = w.zone2_duration_sec or 0.0
            z4 = w.zone4_duration_sec or 0.0
            z5 = w.zone5_duration_sec or 0.0

            total_cardio_sec += dur
            zone2_sec += z2
            zone4_sec += z4
            zone5_sec += z5

            # Weekly bucket grouping in athlete's local IANA timezone (keyed by local Monday date)
            local_d = _to_local_date(w.start_time_utc, tz_name)
            w_start = local_d - timedelta(days=local_d.weekday())
            if w_start not in weekly_buckets:
                weekly_buckets[w_start] = {
                    "miles": 0.0,
                    "zone2_hours": 0.0,
                    "zone2_minutes": 0.0,
                    "zone4_minutes": 0.0,
                    "zone5_minutes": 0.0,
                }
            weekly_buckets[w_start]["miles"] += dist * 0.000621371
            weekly_buckets[w_start]["zone2_hours"] += z2 / 3600.0
            weekly_buckets[w_start]["zone2_minutes"] += z2 / 60.0
            weekly_buckets[w_start]["zone4_minutes"] += z4 / 60.0
            weekly_buckets[w_start]["zone5_minutes"] += z5 / 60.0

        total_cardio_min = round(total_cardio_sec / 60.0, 1)
        zone2_min = round(zone2_sec / 60.0, 1)
        zone4_min = round(zone4_sec / 60.0, 1)
        zone5_min = round(zone5_sec / 60.0, 1)
        zone2_pct = round((zone2_sec / total_cardio_sec * 100.0) if total_cardio_sec > 0 else 0.0, 1)
        zone5_pct = round((zone5_sec / total_cardio_sec * 100.0) if total_cardio_sec > 0 else 0.0, 1)

        weekly_trend = [
            WeeklyCardioBucket(
                week_label=w_start.strftime("%b %d"),
                miles=round(data["miles"], 2),
                zone2_hours=round(data["zone2_hours"], 2),
                zone2_minutes=round(data["zone2_minutes"], 1),
                zone4_minutes=round(data["zone4_minutes"], 1),
                zone5_minutes=round(data["zone5_minutes"], 1),
            )
            for w_start, data in sorted(weekly_buckets.items(), key=lambda item: item[0])
        ]

        # 2. Resistance Volume Aggregation (by canonical Push / Pull / Legs / Abs + conditional Other)
        stmt_strength = (
            select(StrengthSet, StrengthExercise, WorkoutSession.start_time_utc)
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
        res_strength = await session.execute(stmt_strength)
        strength_rows = res_strength.all()

        # Compute effective weeks in window (handles 'all' window from 1970-01-01 cleanly)
        if start_time.year < 1980:
            candidate_starts = [w.start_time_utc for w in cardio_workouts] + [row[2] for row in strength_rows]
            effective_start = min(candidate_starts) if candidate_starts else end_time
        else:
            effective_start = start_time
        window_days = max(1.0, (end_time - effective_start).total_seconds() / 86400.0)
        weeks_in_window = max(1.0, window_days / 7.0)

        cardio_summary = CardioVolumeSummary(
            total_cardio_minutes=total_cardio_min,
            zone2_minutes=zone2_min,
            zone4_minutes=zone4_min,
            zone5_minutes=zone5_min,
            zone2_percentage=zone2_pct,
            zone5_percentage=zone5_pct,
            zone2_weekly_goal_minutes=self.WEEKLY_ZONE2_GOAL_MINUTES,
            vo2max_weekly_goal_minutes=self.WEEKLY_VO2MAX_GOAL_MINUTES,
            zone2_avg_weekly_minutes=round(zone2_min / weeks_in_window, 1),
            zone4_avg_weekly_minutes=round(zone4_min / weeks_in_window, 1),
            vo2max_avg_weekly_minutes=round(zone5_min / weeks_in_window, 1),
            weekly_trend=weekly_trend,
        )

        muscle_data: Dict[str, Dict] = {
            slug: {
                "display_name": display,
                "working_sets": 0,
                "total_reps": 0,
                "top_exercise_name": None,
                "top_weight_lbs": None,
                "top_reps": None,
                "estimated_1rm_lbs": None,
            }
            for slug, display in self.CANONICAL_MUSCLE_GROUPS.items()
        }
        muscle_data["other"] = {
            "display_name": "Other",
            "working_sets": 0,
            "total_reps": 0,
            "top_exercise_name": None,
            "top_weight_lbs": None,
            "top_reps": None,
            "estimated_1rm_lbs": None,
        }

        for s_set, exercise, _ in strength_rows:
            if s_set.is_warmup:
                continue

            slug, _ = self.normalize_muscle_group(exercise.primary_muscle_group, exercise.canonical_name)
            if slug not in muscle_data:
                slug = "other"

            unit = (s_set.weight_unit or "lbs").lower()
            conv = KG_TO_LBS if unit == "kg" else 1.0

            reps = s_set.reps_completed or 0
            is_bw = s_set.is_bodyweight or exercise.is_bodyweight
            if is_bw:
                wt = (float(s_set.added_weight) if s_set.added_weight is not None else 0.0) * conv
            else:
                wt = (float(s_set.weight) if s_set.weight is not None else 0.0) * conv

            m = muscle_data[slug]
            m["working_sets"] += 1
            m["total_reps"] += reps

            est_1rm = self.calculate_estimated_1rm(wt, reps)

            # Pair top_exercise_name, top_weight_lbs, top_reps, and estimated_1rm_lbs from the SAME winning set
            cur_1rm = m["estimated_1rm_lbs"]
            cur_wt = m["top_weight_lbs"]
            is_new_top = False
            if est_1rm is not None:
                if cur_1rm is None or est_1rm > cur_1rm or (est_1rm == cur_1rm and (cur_wt is None or wt > cur_wt)):
                    is_new_top = True
            elif cur_1rm is None and (cur_wt is None or wt > cur_wt):
                is_new_top = True

            if is_new_top:
                m["top_weight_lbs"] = round(wt, 1)
                m["top_reps"] = reps
                m["top_exercise_name"] = exercise.canonical_name
                m["estimated_1rm_lbs"] = est_1rm

        resistance_summary = []
        for slug, info in muscle_data.items():
            # Surface "Other" only when unmapped working sets exist
            if slug == "other" and info["working_sets"] == 0:
                continue
            goal_sets = self.WEEKLY_STRENGTH_GOAL_SETS if slug != "other" else 0.0
            weekly_avg = round(info["working_sets"] / weeks_in_window, 1)
            progress_pct = round((weekly_avg / goal_sets) * 100.0, 1) if goal_sets > 0 else 0.0
            resistance_summary.append(
                MuscleGroupVolumeSummary(
                    muscle_group=cast(Literal["push", "pull", "legs", "abs", "other"], slug),
                    display_name=info["display_name"],
                    working_sets=info["working_sets"],
                    weekly_avg_sets=weekly_avg,
                    weekly_goal_sets=goal_sets,
                    goal_progress_pct=progress_pct,
                    total_reps=info["total_reps"],
                    top_exercise_name=info["top_exercise_name"],
                    top_weight_lbs=info["top_weight_lbs"],
                    top_reps=info["top_reps"],
                    estimated_1rm_lbs=info["estimated_1rm_lbs"],
                )
            )

        return DashboardMacroResponse(
            cardio=cardio_summary,
            resistance=resistance_summary,
        )

    async def get_workout_detail_telemetry(
        self,
        session: AsyncSession,
        workout_id: uuid.UUID,
    ) -> Optional[WorkoutDetailTelemetry]:
        """Returns synchronized continuous HR & Pace telemetry, structured splits, notes, and strength working sets."""
        from sqlalchemy.orm import selectinload
        from src.models.strength_set import StrengthSet

        stmt = (
            select(WorkoutSession)
            .options(
                selectinload(WorkoutSession.heart_rate_samples),
                selectinload(WorkoutSession.splits),
                selectinload(WorkoutSession.gps_route_points),
                selectinload(WorkoutSession.strength_sets).selectinload(StrengthSet.exercise),
            )
            .where(WorkoutSession.id == workout_id)
        )
        res = await session.execute(stmt)
        w = res.scalar_one_or_none()
        if not w:
            return None

        # Build split boundaries
        split_intervals = []
        cur_elapsed = 0.0
        sorted_splits = sorted(w.splits, key=lambda s: s.split_index)
        for sp in sorted_splits:
            sp_start = cur_elapsed
            sp_end = cur_elapsed + (sp.duration_sec or 0.0)
            split_intervals.append((sp, sp_start, sp_end))
            cur_elapsed = sp_end

        # 1. Check for Speed Samples in raw_summary (e.g. from Polar speed sample-type 1)
        speed_samples_map: dict[float, float] = {}
        if w.raw_summary and "speed_samples" in w.raw_summary and isinstance(w.raw_summary["speed_samples"], list):
            for ss in w.raw_summary["speed_samples"]:
                s_sec = float(ss.get("elapsed_sec", 0))
                s_pace = ss.get("pace_sec")
                if s_pace:
                    p_val = float(s_pace)
                    # Filter initial GPS-lock slowdown spikes so pace chart axis stays scaled cleanly
                    if p_val > 900.0:
                        continue
                    if w.avg_pace_sec_per_km and w.avg_pace_sec_per_km < 540 and s_sec < 45.0 and p_val > w.avg_pace_sec_per_km * 1.6:
                        continue
                    speed_samples_map[s_sec] = round(p_val, 1)

        # 2. Check for GPS points (compute rolling Haversine pace)
        gps_pace_map: dict[float, float] = {}
        sorted_gps = sorted(w.gps_route_points, key=lambda p: p.elapsed_sec)
        if len(sorted_gps) >= 2:
            def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
                R = 6371000.0
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
                c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
                return R * c

            for i in range(1, len(sorted_gps)):
                p_prev = sorted_gps[i - 1]
                p_curr = sorted_gps[i]
                dt = p_curr.elapsed_sec - p_prev.elapsed_sec
                if dt >= 1.0:
                    dist = haversine_m(p_prev.latitude, p_prev.longitude, p_curr.latitude, p_curr.longitude)
                    speed_mps = dist / dt
                    if 0.5 <= speed_mps <= 12.0:
                        gps_pace_map[p_curr.elapsed_sec] = round(1000.0 / speed_mps, 1)

        # 3. Check for Concept2 Stroke Data (interval-aligned so multi-interval timestamps never stack)
        aligned_strokes: list[dict] = []
        strokes_by_interval: dict[int, list[dict]] = defaultdict(list)
        if w.raw_summary and "strokes" in w.raw_summary and isinstance(w.raw_summary["strokes"], list):
            aligned_strokes = parse_concept2_strokes(w.raw_summary)
            for st_item in aligned_strokes:
                strokes_by_interval[st_item["interval_index"]].append(st_item)

        sorted_hr = sorted(w.heart_rate_samples, key=lambda x: x.elapsed_sec)

        def _default_split_pace(sp) -> Optional[float]:
            if w.discipline == "indoor_row":
                return sp.avg_split_sec_per_500m
            elif w.discipline in ("outdoor_run", "erg_bike"):
                return sp.avg_pace_sec_per_km
            return None

        import bisect

        sorted_speed_keys = sorted(speed_samples_map.keys())
        sorted_gps_keys = sorted(gps_pace_map.keys())
        has_split_pace = any(_default_split_pace(sp) is not None for sp, _, _ in split_intervals)

        if aligned_strokes:
            pace_source = "strokes"
        elif sorted_speed_keys:
            pace_source = "speed_samples"
        elif sorted_gps_keys:
            pace_source = "gps"
        elif has_split_pace:
            pace_source = "splits"
        elif (w.discipline == "indoor_row" and w.avg_split_sec_per_500m) or (
            w.discipline in ("outdoor_run", "erg_bike") and w.avg_pace_sec_per_km
        ):
            pace_source = "session_average"
        else:
            pace_source = "none"

        def _lookup_nearest(sorted_keys: list[float], val_map: dict[float, float], sec: float, max_diff: float) -> Optional[float]:
            if not sorted_keys:
                return None
            idx = bisect.bisect_left(sorted_keys, sec)
            candidates = []
            if idx < len(sorted_keys):
                candidates.append(sorted_keys[idx])
            if idx > 0:
                candidates.append(sorted_keys[idx - 1])
            best = min(candidates, key=lambda k: abs(k - sec))
            return val_map[best] if abs(best - sec) <= max_diff else None

        def get_pace_for_elapsed(sec: float) -> Optional[float]:
            # A. Real Polar speed samples
            if sorted_speed_keys:
                return _lookup_nearest(sorted_speed_keys, speed_samples_map, sec, 5.0)

            # B. Real GPS calculated pace
            if sorted_gps_keys:
                return _lookup_nearest(sorted_gps_keys, gps_pace_map, sec, 15.0)

            # C. Measured split/interval pace
            for sp, st, en in split_intervals:
                if st <= sec <= en:
                    return _default_split_pace(sp)

            # Never fabricate continuous pace curves from heart rate!
            return None

        # Build continuous time_series
        if aligned_strokes:
            time_series: list[TelemetryPoint] = []
            # Build lookup of rest splits to insert explicit rest recovery markers / pace breaks
            rest_splits = [(sp, st, en) for sp, st, en in split_intervals if sp.split_type == "rest"]
            rest_idx = 0
            for st_item in aligned_strokes:
                el = st_item["elapsed_sec"]
                while rest_idx < len(rest_splits) and rest_splits[rest_idx][2] <= el:
                    r_sp, r_st, r_en = rest_splits[rest_idx]
                    # Break pace/SPM lines cleanly during rest; connect HR down to recovery HR
                    time_series.append(TelemetryPoint(elapsed_sec=round(r_st + 0.1, 1), heart_rate=None, pace_sec=None, cadence_spm=None))
                    if r_sp.avg_heart_rate:
                        time_series.append(
                            TelemetryPoint(
                                elapsed_sec=round(r_en - 0.1, 1),
                                heart_rate=r_sp.avg_heart_rate,
                                pace_sec=None,
                                cadence_spm=None,
                            )
                        )
                    rest_idx += 1

                time_series.append(
                    TelemetryPoint(
                        elapsed_sec=el,
                        heart_rate=st_item["heart_rate"] or w.avg_heart_rate,
                        pace_sec=st_item["pace_sec"],
                        cadence_spm=st_item["cadence_spm"],
                    )
                )
        elif sorted_hr:
            time_series = [
                TelemetryPoint(
                    elapsed_sec=s.elapsed_sec,
                    heart_rate=s.bpm,
                    pace_sec=get_pace_for_elapsed(s.elapsed_sec),
                )
                for s in sorted_hr
            ]
        elif split_intervals:
            time_series = []
            for sp, st, en in split_intervals:
                dur = en - st
                step = 10.0
                n = max(1, int(dur / step))
                for i in range(n):
                    t = st + (i * step)
                    time_series.append(
                        TelemetryPoint(
                            elapsed_sec=round(t, 1),
                            heart_rate=sp.avg_heart_rate or w.avg_heart_rate,
                            pace_sec=_default_split_pace(sp),
                        )
                    )
        else:
            time_series = []

        # Enrich split details with ending/max HR from raw_summary & per-split stroke series
        raw_intervals_meta: list[dict[str, Any]] = []
        if w.raw_summary and isinstance(w.raw_summary, dict):
            raw_intervals_meta = (
                w.raw_summary.get("intervals")
                or w.raw_summary.get("workout", {}).get("intervals")
                or w.raw_summary.get("workout", {}).get("splits")
                or []
            )

        splits_detail: list[IntervalSplitDetail] = []
        work_seq_idx = 0
        for sp, st, en in split_intervals:
            is_work_or_lap = sp.split_type in ("interval", "work", "lap")
            ending_hr: int | None = None
            peak_hr: int | None = None
            split_samples: list[NormalizedSample] = []

            if is_work_or_lap:
                work_seq_idx += 1
                if work_seq_idx - 1 < len(raw_intervals_meta):
                    meta_hr = raw_intervals_meta[work_seq_idx - 1].get("heart_rate")
                    if isinstance(meta_hr, dict):
                        ending_hr = int(meta_hr["ending"]) if meta_hr.get("ending") is not None else None
                        peak_hr = int(meta_hr["max"]) if meta_hr.get("max") is not None else None

                # Extract relative-time telemetry curve for this single split/interval
                if sp.split_type in ("interval", "work") and work_seq_idx in strokes_by_interval:
                    split_samples = [
                        NormalizedSample(
                            set_elapsed_sec=s["set_elapsed_sec"],
                            heart_rate=s["heart_rate"],
                            pace_sec=s["pace_sec"],
                            cadence_spm=s["cadence_spm"],
                        )
                        for s in strokes_by_interval[work_seq_idx]
                    ]
                else:
                    split_samples = [
                        NormalizedSample(
                            set_elapsed_sec=round(pt.elapsed_sec - st, 1),
                            heart_rate=pt.heart_rate,
                            pace_sec=pt.pace_sec if pt.pace_sec is not None else _default_split_pace(sp),
                            cadence_spm=pt.cadence_spm,
                        )
                        for pt in time_series
                        if st <= pt.elapsed_sec <= en and (pt.heart_rate is not None or pt.pace_sec is not None)
                    ]

            splits_detail.append(
                IntervalSplitDetail(
                    split_index=sp.split_index,
                    split_type=sp.split_type,
                    duration_sec=sp.duration_sec,
                    distance_m=sp.distance_m,
                    avg_heart_rate=sp.avg_heart_rate,
                    ending_heart_rate=ending_hr,
                    peak_heart_rate=peak_hr,
                    avg_pace_sec=_default_split_pace(sp),
                    avg_power_watts=sp.avg_power_watts,
                    avg_cadence_spm=sp.avg_cadence_spm,
                    samples=split_samples,
                )
            )

        # Consistency analysis for work intervals (reuses each split's extracted samples)
        work_details = [sd for sd in splits_detail if sd.split_type in ("interval", "work")]
        consistency_analysis = None

        if len(work_details) >= 2:
            superimposed = []
            work_paces = []
            for idx, sd in enumerate(work_details, start=1):
                set_samples = list(sd.samples)
                if not set_samples and sd.avg_heart_rate:
                    set_samples = [
                        NormalizedSample(set_elapsed_sec=0.0, heart_rate=sd.avg_heart_rate, pace_sec=sd.avg_pace_sec),
                        NormalizedSample(set_elapsed_sec=sd.duration_sec, heart_rate=sd.avg_heart_rate, pace_sec=sd.avg_pace_sec),
                    ]
                superimposed.append(IntervalConsistencySet(set_index=idx, points=set_samples))
                if sd.avg_pace_sec:
                    work_paces.append(sd.avg_pace_sec)

            # Compute pace variance %
            variance_pct = 0.0
            if len(work_paces) >= 2:
                mean_p = sum(work_paces) / len(work_paces)
                variance = (sum((p - mean_p) ** 2 for p in work_paces) / len(work_paces)) ** 0.5
                variance_pct = round((variance / mean_p) * 100.0, 2)

            consistency_analysis = IntervalConsistencyAnalysis(
                is_consistent=(variance_pct <= 3.5),
                pace_variance_pct=variance_pct,
                superimposed_curves=superimposed,
            )

        rest_dist = None
        if w.raw_summary and isinstance(w.raw_summary, dict) and w.raw_summary.get("rest_distance") is not None:
            rest_dist = float(w.raw_summary["rest_distance"])

        route_points = [
            GPSRoutePointSchema(
                elapsed_sec=p.elapsed_sec,
                latitude=p.latitude,
                longitude=p.longitude,
                altitude_m=p.altitude_m,
            )
            for p in sorted_gps
        ]

        hr_zone_seconds = {
            "zone1": round(w.zone1_duration_sec or 0.0, 1),
            "zone2": round(w.zone2_duration_sec or 0.0, 1),
            "zone3": round(w.zone3_duration_sec or 0.0, 1),
            "zone4": round(w.zone4_duration_sec or 0.0, 1),
            "zone5": round(w.zone5_duration_sec or 0.0, 1),
        }

        sorted_strength_sets = sorted(
            w.strength_sets or [],
            key=lambda s: (s.completed_at or datetime.min.replace(tzinfo=timezone.utc), s.set_index),
        )
        strength_sets_detail: list[StrengthSetDetail] = []
        for s_set in sorted_strength_sets:
            ex = s_set.exercise
            ex_name = ex.canonical_name if ex else "Unknown Exercise"
            cat_slug, _ = self.normalize_muscle_group(ex.primary_muscle_group if ex else None, ex_name)
            unit = (s_set.weight_unit or "lbs").lower()
            conv = KG_TO_LBS if unit == "kg" else 1.0
            is_bw = bool(s_set.is_bodyweight or (ex.is_bodyweight if ex else False))
            added_wt = round(float(s_set.added_weight) * conv, 1) if (is_bw and s_set.added_weight is not None) else None
            raw_wt = float(s_set.added_weight) if (is_bw and s_set.added_weight is not None) else float(s_set.weight or 0.0)
            strength_sets_detail.append(
                StrengthSetDetail(
                    exercise_name=ex_name,
                    category=cat_slug,
                    set_index=s_set.set_index,
                    reps_completed=s_set.reps_completed,
                    weight_lbs=round(raw_wt * conv, 1),
                    is_bodyweight=is_bw,
                    added_weight_lbs=added_wt,
                    rpe=float(s_set.rpe) if s_set.rpe is not None else None,
                    is_warmup=bool(s_set.is_warmup),
                )
            )

        return WorkoutDetailTelemetry(
            workout_id=w.id,
            discipline=w.discipline,
            title=w.title,
            user_notes=w.user_notes,
            total_duration_sec=w.total_duration_sec,
            total_distance_m=w.total_distance_m,
            total_calories=w.total_calories,
            avg_heart_rate=w.avg_heart_rate,
            max_heart_rate=w.max_heart_rate,
            avg_pace_sec_per_km=w.avg_pace_sec_per_km,
            elevation_gain_m=w.elevation_gain_m,
            elevation_loss_m=w.elevation_loss_m,
            rest_distance_m=rest_dist,
            pace_source=pace_source,
            hr_zone_seconds=hr_zone_seconds,
            time_series=time_series,
            splits=splits_detail,
            strength_sets=strength_sets_detail,
            route_points=route_points,
            interval_consistency=consistency_analysis,
        )

    async def get_cardio_metrics(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        tz_name: str = "UTC",
    ) -> CardioAnalyticsResponse:
        """Aggregates cardiovascular volume, Zone 2 duration, and chronologically sorted weekly trends."""
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

        weekly_buckets: Dict[date, Dict[str, float]] = defaultdict(
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

            # Weekly bucket keyed by athlete-local Monday date for chronological cross-year sorting
            local_d = _to_local_date(w.start_time_utc, tz_name)
            monday = local_d - timedelta(days=local_d.weekday())
            miles = (dist / 1000.0) * KM_TO_MILES
            weekly_buckets[monday]["miles"] += miles
            weekly_buckets[monday]["zone2_hours"] += z2 / 3600.0

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
                week_label=f"W{monday.isocalendar()[1]:02d} ({monday.strftime('%m/%d')})",
                miles=round(data["miles"], 2),
                zone2_hours=round(data["zone2_hours"], 2),
            )
            for monday, data in sorted(weekly_buckets.items(), key=lambda item: item[0])
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

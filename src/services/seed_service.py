"""Service for seeding realistic multi-modal sample workouts and safely purging demo data."""

from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    CoachingPhilosophy,
    ExerciseAlias,
    GPSRoutePoint,
    HeartRateSample,
    StrengthExercise,
    StrengthSet,
    User,
    UserHeartRateProfile,
    WorkoutSession,
    WorkoutSplit,
)


class SeedService:
    @classmethod
    async def ensure_default_athlete_and_philosophy(cls, db: AsyncSession) -> User:
        """Ensures a default user with HR profile and active coaching philosophy exists."""
        res = await db.execute(select(User))
        user = res.scalars().first()
        if not user:
            user = User(id=uuid.uuid4())
            db.add(user)
            await db.flush()

        res_hr = await db.execute(select(UserHeartRateProfile).where(UserHeartRateProfile.user_id == user.id))
        hr = res_hr.scalars().first()
        if not hr:
            default_max_hr = 185
            hr = UserHeartRateProfile(
                id=uuid.uuid4(),
                user_id=user.id,
                resting_hr=50,
                max_hr=default_max_hr,
                zone1_min=round(default_max_hr * 0.50),
                zone1_max=round(default_max_hr * 0.60),
                zone2_min=round(default_max_hr * 0.60),
                zone2_max=round(default_max_hr * 0.70),
                zone3_min=round(default_max_hr * 0.70),
                zone3_max=round(default_max_hr * 0.80),
                zone4_min=round(default_max_hr * 0.80),
                zone4_max=round(default_max_hr * 0.90),
                zone5_min=round(default_max_hr * 0.90),
                zone5_max=default_max_hr,
            )
            db.add(hr)

        res_phil = await db.execute(select(CoachingPhilosophy).where(CoachingPhilosophy.user_id == user.id))
        phil = res_phil.scalars().first()
        if not phil:
            phil = CoachingPhilosophy(
                id=uuid.uuid4(),
                user_id=user.id,
                name="Polarized 80/20 Base + Progressive Overload",
                description="80% aerobic Zone 2 endurance base with progressive overload on main compound lifts.",
                target_zone2_pct=80.0,
                max_weekly_volume_ramp_pct=10.0,
                max_rpe_threshold=8.5,
                min_rest_days_per_week=2,
                primary_modality="hybrid",
                is_active=True,
            )
            db.add(phil)

        await db.commit()
        await db.refresh(user)
        return user

    @classmethod
    async def ensure_default_exercises(cls, db: AsyncSession) -> dict[str, StrengthExercise]:
        """Ensures standard strength exercises exist in the catalog."""
        exercises = {
            "bench_press": {
                "name": "Barbell Bench Press",
                "slug": "barbell-bench-press",
                "category": "barbell",
                "muscle": "chest",
                "bodyweight": False,
            },
            "squat": {
                "name": "Barbell Back Squat",
                "slug": "barbell-back-squat",
                "category": "barbell",
                "muscle": "quadriceps",
                "bodyweight": False,
            },
            "pull_up": {
                "name": "Pull-up",
                "slug": "pull-up",
                "category": "bodyweight",
                "muscle": "lats",
                "bodyweight": True,
            },
            "hanging_leg_raise": {
                "name": "Hanging Leg Raise",
                "slug": "hanging-leg-raise",
                "category": "bodyweight",
                "muscle": "abs",
                "bodyweight": True,
            },
        }

        catalog = {}
        for key, data in exercises.items():
            q = select(StrengthExercise).where(StrengthExercise.slug == data["slug"])
            res = await db.execute(q)
            ex = res.scalars().first()
            if not ex:
                ex = StrengthExercise(
                    id=uuid.uuid4(),
                    canonical_name=data["name"],
                    slug=data["slug"],
                    category=data["category"],
                    primary_muscle_group=data["muscle"],
                    is_bodyweight=data["bodyweight"],
                    default_unit="lbs",
                )
                db.add(ex)
                await db.flush()
                alias = ExerciseAlias(id=uuid.uuid4(), exercise_id=ex.id, alias=data["name"].lower())
                db.add(alias)
            catalog[key] = ex
        await db.commit()
        return catalog

    @classmethod
    async def seed_sample_workouts(cls, db: AsyncSession) -> tuple[int, int]:
        """Seeds realistic running, rowing, bike erg, and strength sessions with is_demo=True.
        
        Returns:
            (workouts_created, strength_sets_created)
        """
        user = await cls.ensure_default_athlete_and_philosophy(db)
        ex_catalog = await cls.ensure_default_exercises(db)

        # Avoid duplicating if already seeded
        q_existing = select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.is_demo == True,
        )
        res_existing = await db.execute(q_existing)
        if len(res_existing.scalars().all()) >= 5:
            # Already seeded
            return 0, 0

        now = datetime.now(timezone.utc)
        workouts_count = 0
        sets_count = 0

        # 1. Long Zone 2 Run (Polar) - 3 days ago
        w1_time = now - timedelta(days=3)
        w1 = WorkoutSession(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="polar",
            external_id=f"demo_polar_run_1_{int(w1_time.timestamp())}",
            discipline="outdoor_run",
            title="Polar Long Aerobic Base Run",
            start_time_utc=w1_time,
            local_timezone="America/Los_Angeles",
            total_duration_sec=3600.0,
            active_duration_sec=3600.0,
            total_distance_m=10000.0,
            total_calories=750,
            avg_heart_rate=135,
            max_heart_rate=152,
            zone1_duration_sec=400.0,
            zone2_duration_sec=2900.0,  # ~80% Zone 2
            zone3_duration_sec=300.0,
            zone4_duration_sec=0.0,
            zone5_duration_sec=0.0,
            avg_pace_sec_per_km=360.0,
            elevation_gain_m=65.0,
            elevation_loss_m=62.0,
            user_notes="Relaxed aerobic base effort focusing on nasal breathing and smooth cadence.",
            is_demo=True,
            status="active",
        )
        db.add(w1)
        workouts_count += 1

        # Add sample HR and GPS points for w1
        for i in range(10):
            pt_time = w1_time + timedelta(seconds=i * 360)
            hr_sample = HeartRateSample(
                workout_id=w1.id,
                timestamp_utc=pt_time,
                elapsed_sec=float(i * 360),
                bpm=130 + (i % 8),
            )
            db.add(hr_sample)
            gps_pt = GPSRoutePoint(
                workout_id=w1.id,
                timestamp_utc=pt_time,
                elapsed_sec=float(i * 360),
                latitude=37.7749 + (i * 0.001),
                longitude=-122.4194 + (i * 0.001),
                altitude_m=15.0 + float(i),
            )
            db.add(gps_pt)

        # 2. Recovery Zone 2 Run - Yesterday
        w2_time = now - timedelta(days=1)
        w2 = WorkoutSession(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="polar",
            external_id=f"demo_polar_run_2_{int(w2_time.timestamp())}",
            discipline="outdoor_run",
            title="Polar Zone 2 Recovery Run",
            start_time_utc=w2_time,
            local_timezone="America/Los_Angeles",
            total_duration_sec=1800.0,
            active_duration_sec=1800.0,
            total_distance_m=5000.0,
            total_calories=380,
            avg_heart_rate=128,
            max_heart_rate=140,
            zone1_duration_sec=200.0,
            zone2_duration_sec=1600.0,
            zone3_duration_sec=0.0,
            zone4_duration_sec=0.0,
            zone5_duration_sec=0.0,
            avg_pace_sec_per_km=360.0,
            is_demo=True,
            status="active",
        )
        db.add(w2)
        workouts_count += 1

        # 3. Concept2 Indoor Rower 5k - 4 days ago
        w3_time = now - timedelta(days=4)
        w3 = WorkoutSession(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="concept2",
            external_id=f"demo_c2_row_1_{int(w3_time.timestamp())}",
            discipline="indoor_row",
            title="Concept2 5000m Steady State Row",
            start_time_utc=w3_time,
            local_timezone="America/Los_Angeles",
            total_duration_sec=1200.0,
            active_duration_sec=1200.0,
            total_distance_m=5000.0,
            total_calories=260,
            avg_heart_rate=138,
            max_heart_rate=150,
            zone2_duration_sec=1100.0,
            zone3_duration_sec=100.0,
            total_strokes=540,
            avg_cadence_spm=22.5,
            avg_power_watts=205.0,
            avg_split_sec_per_500m=120.0,  # 2:00.0
            avg_drag_factor=125,
            is_demo=True,
            status="active",
        )
        db.add(w3)
        workouts_count += 1

        # 4. Concept2 Erg Bike 15k - 2 days ago
        w4_time = now - timedelta(days=2)
        w4 = WorkoutSession(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="concept2",
            external_id=f"demo_c2_bike_1_{int(w4_time.timestamp())}",
            discipline="erg_bike",
            title="Concept2 BikeErg Aerobic Cruise",
            start_time_utc=w4_time,
            local_timezone="America/Los_Angeles",
            total_duration_sec=1800.0,
            active_duration_sec=1800.0,
            total_distance_m=15000.0,
            total_calories=320,
            avg_heart_rate=132,
            max_heart_rate=145,
            zone2_duration_sec=1650.0,
            avg_power_watts=190.0,
            avg_cadence_spm=88.0,
            avg_drag_factor=105,
            is_demo=True,
            status="active",
        )
        db.add(w4)
        workouts_count += 1

        # 5. Gym Strength Full Body (Push/Pull/Legs/Abs) Session - Today
        w5_time = now - timedelta(hours=3)
        w5 = WorkoutSession(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="gym_mode",
            external_id=f"demo_gym_strength_1_{int(w5_time.timestamp())}",
            discipline="strength",
            title="Gym Strength: Push / Pull / Legs / Abs",
            start_time_utc=w5_time,
            local_timezone="America/Los_Angeles",
            total_duration_sec=2700.0,
            active_duration_sec=2700.0,
            total_distance_m=0.0,
            total_calories=310,
            user_notes="Solid bar speed on bench and squats; controlled weighted pull-ups + core finisher.",
            is_demo=True,
            status="active",
        )
        db.add(w5)
        workouts_count += 1

        # 7 seeded sets covering all 4 canonical categories (Push, Pull, Legs, Abs)
        bench_sets = [
            (1, 8, 185.0, 7.5, False),
            (2, 6, 205.0, 8.5, False),
        ]
        for s_idx, reps, wt, rpe_val, is_wu in bench_sets:
            s = StrengthSet(
                id=uuid.uuid4(),
                workout_session_id=w5.id,
                exercise_id=ex_catalog["bench_press"].id,
                set_index=s_idx,
                reps_completed=reps,
                weight=wt,
                weight_unit="lbs",
                is_bodyweight=False,
                added_weight=0.0,
                rpe=rpe_val,
                is_warmup=is_wu,
                idempotency_key=f"demo_bench_{w5.id}_{s_idx}",
            )
            db.add(s)
            sets_count += 1

        pullup_sets = [
            (1, 8, 15.0, 8.0, False),  # +15 lbs
            (2, 6, 25.0, 8.5, False),  # +25 lbs
        ]
        for s_idx, reps, added_wt, rpe_val, is_wu in pullup_sets:
            s = StrengthSet(
                id=uuid.uuid4(),
                workout_session_id=w5.id,
                exercise_id=ex_catalog["pull_up"].id,
                set_index=s_idx,
                reps_completed=reps,
                weight=added_wt,
                weight_unit="lbs",
                is_bodyweight=True,
                added_weight=added_wt,
                rpe=rpe_val,
                is_warmup=is_wu,
                idempotency_key=f"demo_pullup_{w5.id}_{s_idx}",
            )
            db.add(s)
            sets_count += 1

        squat_sets = [
            (1, 5, 225.0, 7.5, False),
            (2, 5, 245.0, 8.5, False),
        ]
        for s_idx, reps, wt, rpe_val, is_wu in squat_sets:
            s = StrengthSet(
                id=uuid.uuid4(),
                workout_session_id=w5.id,
                exercise_id=ex_catalog["squat"].id,
                set_index=s_idx,
                reps_completed=reps,
                weight=wt,
                weight_unit="lbs",
                is_bodyweight=False,
                added_weight=0.0,
                rpe=rpe_val,
                is_warmup=is_wu,
                idempotency_key=f"demo_squat_{w5.id}_{s_idx}",
            )
            db.add(s)
            sets_count += 1

        abs_sets = [
            (1, 15, 0.0, 8.0, False),
        ]
        for s_idx, reps, added_wt, rpe_val, is_wu in abs_sets:
            s = StrengthSet(
                id=uuid.uuid4(),
                workout_session_id=w5.id,
                exercise_id=ex_catalog["hanging_leg_raise"].id,
                set_index=s_idx,
                reps_completed=reps,
                weight=added_wt,
                weight_unit="lbs",
                is_bodyweight=True,
                added_weight=added_wt,
                rpe=rpe_val,
                is_warmup=is_wu,
                idempotency_key=f"demo_abs_{w5.id}_{s_idx}",
            )
            db.add(s)
            sets_count += 1

        # 6. Concept2 4x4min VO2 Max Interval Rower (4min rest) - 3 days ago
        w6_time = now - timedelta(days=3)
        w6 = WorkoutSession(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="concept2",
            external_id=f"demo_c2_interval_row_1_{int(w6_time.timestamp())}",
            discipline="indoor_row",
            title="Concept2 4x4min VO2 Max Intervals (4min rest)",
            start_time_utc=w6_time,
            local_timezone="America/Los_Angeles",
            total_duration_sec=1680.0,  # 28 mins total
            active_duration_sec=960.0,   # 16 mins work
            total_distance_m=4220.0,
            total_calories=390,
            avg_heart_rate=156,
            max_heart_rate=184,
            zone1_duration_sec=200.0,
            zone2_duration_sec=400.0,
            zone3_duration_sec=180.0,
            zone4_duration_sec=500.0,
            zone5_duration_sec=400.0,   # VO2 max stimulus
            total_strokes=448,
            avg_cadence_spm=28.0,
            avg_power_watts=245.0,
            avg_split_sec_per_500m=113.7,  # 1:53.7
            avg_drag_factor=130,
            is_demo=True,
            status="active",
        )
        db.add(w6)
        workouts_count += 1

        # Splits for w6: 4 work intervals and 3 rest intervals
        intervals_data = [
            (1, "interval", 240.0, 1055.0, 113.7, 245.0, 28.0, 162),
            (2, "rest", 240.0, 0.0, None, 0.0, 0.0, 132),
            (3, "interval", 240.0, 1060.0, 113.2, 248.0, 28.5, 166),
            (4, "rest", 240.0, 0.0, None, 0.0, 0.0, 136),
            (5, "interval", 240.0, 1053.0, 113.9, 243.0, 28.0, 169),
            (6, "rest", 240.0, 0.0, None, 0.0, 0.0, 138),
            (7, "interval", 240.0, 1052.0, 114.1, 242.0, 28.0, 172),
        ]
        for sp_idx, sp_type, sp_dur, sp_dist, sp_pace, sp_pwr, sp_cad, sp_hr in intervals_data:
            split_obj = WorkoutSplit(
                id=uuid.uuid4(),
                workout_id=w6.id,
                split_index=sp_idx,
                split_type=sp_type,
                duration_sec=sp_dur,
                distance_m=sp_dist,
                avg_split_sec_per_500m=sp_pace,
                avg_pace_sec_per_km=(sp_pace * 2.0) if sp_pace else None,
                avg_power_watts=sp_pwr,
                avg_cadence_spm=sp_cad,
                avg_heart_rate=sp_hr,
            )
            db.add(split_obj)

        # Telemetry samples for w6: sampled every 15 seconds across 1680s
        for sec in range(0, 1681, 15):
            pt_time = w6_time + timedelta(seconds=sec)
            # Determine if in work or rest interval
            int_idx = sec // 240
            rem_sec = sec % 240
            fraction = rem_sec / 240.0
            
            if int_idx % 2 == 0:
                # Work interval: HR ramps up to peak
                base_hr = 145 + (int_idx * 3)
                peak_hr = 174 + (int_idx * 3)
                bpm_val = int(base_hr + (peak_hr - base_hr) * fraction)
            else:
                # Rest interval: HR drops back down
                peak_hr = 174 + ((int_idx - 1) * 3)
                recover_hr = 130 + (int_idx * 2)
                bpm_val = int(peak_hr - (peak_hr - recover_hr) * fraction)

            hr_sample = HeartRateSample(
                workout_id=w6.id,
                timestamp_utc=pt_time,
                elapsed_sec=float(sec),
                bpm=bpm_val,
            )
            db.add(hr_sample)

        await db.commit()
        return workouts_count, sets_count

    @classmethod
    async def purge_demo_data(cls, db: AsyncSession) -> int:
        """Purges only synthetic workout sessions where is_demo == True."""
        q = delete(WorkoutSession).where(WorkoutSession.is_demo == True)
        res = await db.execute(q)
        await db.commit()
        return res.rowcount

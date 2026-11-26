"""Seed script populating canonical strength exercises and aliases."""

import asyncio
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import async_session_factory
from src.models.exercise import ExerciseAlias, StrengthExercise

EXERCISE_DEFINITIONS: list[dict[str, Any]] = [
    # --- Barbell ---
    {
        "canonical_name": "Barbell Back Squat",
        "slug": "barbell-back-squat",
        "category": "barbell",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["squats", "back squat", "back squats", "barbell squat", "high bar squat", "low bar squat", "squat"],
    },
    {
        "canonical_name": "Barbell Front Squat",
        "slug": "barbell-front-squat",
        "category": "barbell",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["front squat", "front squats", "barbell front squat"],
    },
    {
        "canonical_name": "Barbell Bench Press",
        "slug": "barbell-bench-press",
        "category": "barbell",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["bench", "bench press", "flat bench", "flat barbell bench", "barbell bench"],
    },
    {
        "canonical_name": "Incline Barbell Bench Press",
        "slug": "incline-barbell-bench-press",
        "category": "barbell",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["incline bench", "incline barbell bench", "incline press", "incline barbell press"],
    },
    {
        "canonical_name": "Decline Barbell Bench Press",
        "slug": "decline-barbell-bench-press",
        "category": "barbell",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["decline bench", "decline barbell bench", "decline press"],
    },
    {
        "canonical_name": "Barbell Overhead Press",
        "slug": "barbell-overhead-press",
        "category": "barbell",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["overhead press", "ohp", "military press", "standing barbell press", "barbell shoulder press"],
    },
    {
        "canonical_name": "Barbell Deadlift",
        "slug": "barbell-deadlift",
        "category": "barbell",
        "primary_muscle_group": "hamstrings",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["deadlift", "deadlifts", "conventional deadlift", "conventional deadlifts", "barbell deadlift"],
    },
    {
        "canonical_name": "Sumo Deadlift",
        "slug": "sumo-deadlift",
        "category": "barbell",
        "primary_muscle_group": "hamstrings",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["sumo", "sumo deadlifts", "sumo deadlift"],
    },
    {
        "canonical_name": "Romanian Deadlift",
        "slug": "romanian-deadlift",
        "category": "barbell",
        "primary_muscle_group": "hamstrings",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["rdl", "rdls", "romanian deadlifts", "stiff leg deadlift", "barbell rdl"],
    },
    {
        "canonical_name": "Barbell Bent-Over Row",
        "slug": "barbell-bent-over-row",
        "category": "barbell",
        "primary_muscle_group": "back",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["barbell row", "barbell rows", "bent over row", "bent over rows", "pendlay row"],
    },
    {
        "canonical_name": "Barbell Hip Thrust",
        "slug": "barbell-hip-thrust",
        "category": "barbell",
        "primary_muscle_group": "glutes",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["hip thrust", "hip thrusts", "barbell thrust", "barbell hip thrusts"],
    },
    {
        "canonical_name": "Power Clean",
        "slug": "power-clean",
        "category": "barbell",
        "primary_muscle_group": "full_body",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["clean", "cleans", "power cleans", "barbell clean"],
    },
    {
        "canonical_name": "Clean and Jerk",
        "slug": "clean-and-jerk",
        "category": "barbell",
        "primary_muscle_group": "full_body",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["clean and jerk", "clean & jerk", "c&j"],
    },
    {
        "canonical_name": "Snatch",
        "slug": "snatch",
        "category": "barbell",
        "primary_muscle_group": "full_body",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["snatches", "power snatch", "barbell snatch"],
    },
    {
        "canonical_name": "Push Press",
        "slug": "push-press",
        "category": "barbell",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["push press", "push presses", "barbell push press"],
    },
    {
        "canonical_name": "Barbell Shrug",
        "slug": "barbell-shrug",
        "category": "barbell",
        "primary_muscle_group": "back",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["shrugs", "barbell shrugs", "shrug"],
    },
    {
        "canonical_name": "Barbell Bicep Curl",
        "slug": "barbell-bicep-curl",
        "category": "barbell",
        "primary_muscle_group": "arms",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["barbell curl", "barbell curls", "bicep curl", "bicep curls"],
    },
    {
        "canonical_name": "Skull Crusher",
        "slug": "skull-crusher",
        "category": "barbell",
        "primary_muscle_group": "arms",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["skull crusher", "skull crushers", "lying tricep extension", "french press"],
    },
    {
        "canonical_name": "Barbell Good Morning",
        "slug": "barbell-good-morning",
        "category": "barbell",
        "primary_muscle_group": "hamstrings",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["good morning", "good mornings"],
    },
    {
        "canonical_name": "Zercher Squat",
        "slug": "zercher-squat",
        "category": "barbell",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["zercher", "zercher squats", "zercher squat"],
    },

    # --- Dumbbell ---
    {
        "canonical_name": "Dumbbell Bench Press",
        "slug": "dumbbell-bench-press",
        "category": "dumbbell",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db bench", "dumbbell bench", "db flat bench", "dumbbell bench press"],
    },
    {
        "canonical_name": "Incline Dumbbell Bench Press",
        "slug": "incline-dumbbell-bench-press",
        "category": "dumbbell",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["incline db bench", "incline dumbbell bench", "incline db press", "incline dumbbell press"],
    },
    {
        "canonical_name": "Dumbbell Shoulder Press",
        "slug": "dumbbell-shoulder-press",
        "category": "dumbbell",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db shoulder press", "db press", "dumbbell press", "dumbbell overhead press", "seated db press", "seated dumbbell shoulder press"],
    },
    {
        "canonical_name": "Dumbbell Bicep Curl",
        "slug": "dumbbell-bicep-curl",
        "category": "dumbbell",
        "primary_muscle_group": "arms",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db curls", "dumbbell curls", "db curl", "dumbbell curl", "hammer curl", "hammer curls", "db hammer curls"],
    },
    {
        "canonical_name": "Dumbbell Lateral Raise",
        "slug": "dumbbell-lateral-raise",
        "category": "dumbbell",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["lateral raise", "lateral raises", "side raises", "side raise", "db lateral raise", "dumbbell lateral raises"],
    },
    {
        "canonical_name": "Dumbbell Rear Delt Fly",
        "slug": "dumbbell-rear-delt-fly",
        "category": "dumbbell",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["rear delt fly", "rear delt flyes", "rear delt raises", "reverse fly", "db rear delt fly"],
    },
    {
        "canonical_name": "Dumbbell Row",
        "slug": "dumbbell-row",
        "category": "dumbbell",
        "primary_muscle_group": "back",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db row", "db rows", "single arm dumbbell row", "one arm db row", "dumbbell row", "dumbbell rows"],
    },
    {
        "canonical_name": "Dumbbell Romanian Deadlift",
        "slug": "dumbbell-romanian-deadlift",
        "category": "dumbbell",
        "primary_muscle_group": "hamstrings",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db rdl", "dumbbell rdl", "db rdls", "dumbbell rdls"],
    },
    {
        "canonical_name": "Dumbbell Lunge",
        "slug": "dumbbell-lunge",
        "category": "dumbbell",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db lunges", "dumbbell lunges", "walking lunges", "walking db lunges", "dumbbell lunge"],
    },
    {
        "canonical_name": "Goblet Squat",
        "slug": "goblet-squat",
        "category": "dumbbell",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["goblet squat", "goblet squats", "dumbbell goblet squat"],
    },
    {
        "canonical_name": "Dumbbell Pullover",
        "slug": "dumbbell-pullover",
        "category": "dumbbell",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db pullover", "dumbbell pullovers", "dumbbell pullover"],
    },
    {
        "canonical_name": "Dumbbell Shrug",
        "slug": "dumbbell-shrug",
        "category": "dumbbell",
        "primary_muscle_group": "back",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["db shrugs", "db shrug", "dumbbell shrug", "dumbbell shrugs"],
    },
    {
        "canonical_name": "Dumbbell Tricep Extension",
        "slug": "dumbbell-tricep-extension",
        "category": "dumbbell",
        "primary_muscle_group": "arms",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["overhead db tricep extension", "db tricep extension", "tricep kickbacks", "tricep kickback"],
    },

    # --- Bodyweight & Calisthenics ---
    {
        "canonical_name": "Pull-Up",
        "slug": "pull-up",
        "category": "bodyweight",
        "primary_muscle_group": "back",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["pullup", "pullups", "pull ups", "pull-ups", "weighted pullup", "weighted pullups", "wide grip pullup", "strict pullup", "pull up"],
    },
    {
        "canonical_name": "Chin-Up",
        "slug": "chin-up",
        "category": "bodyweight",
        "primary_muscle_group": "back",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["chinup", "chinups", "chin ups", "chin-ups", "weighted chinup", "reverse grip pullup", "chin up"],
    },
    {
        "canonical_name": "Dip",
        "slug": "dip",
        "category": "bodyweight",
        "primary_muscle_group": "chest",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["dips", "parallel bar dips", "chest dips", "tricep dips", "weighted dips", "weighted dip", "assisted dips", "dip"],
    },
    {
        "canonical_name": "Push-Up",
        "slug": "push-up",
        "category": "bodyweight",
        "primary_muscle_group": "chest",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["pushup", "pushups", "push ups", "push-ups", "weighted pushup", "diamond pushups", "push up"],
    },
    {
        "canonical_name": "Inverted Row",
        "slug": "inverted-row",
        "category": "bodyweight",
        "primary_muscle_group": "back",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["inverted rows", "australian pullups", "bodyweight row", "bodyweight rows"],
    },
    {
        "canonical_name": "Muscle-Up",
        "slug": "muscle-up",
        "category": "bodyweight",
        "primary_muscle_group": "full_body",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["muscleup", "muscleups", "muscle ups", "bar muscle up", "ring muscle up"],
    },
    {
        "canonical_name": "Pistol Squat",
        "slug": "pistol-squat",
        "category": "bodyweight",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["pistol squats", "single leg squat", "pistol squat"],
    },
    {
        "canonical_name": "Handstand Push-Up",
        "slug": "handstand-push-up",
        "category": "bodyweight",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["hspu", "handstand pushups", "handstand push up", "handstand push-ups"],
    },
    {
        "canonical_name": "Hanging Leg Raise",
        "slug": "hanging-leg-raise",
        "category": "bodyweight",
        "primary_muscle_group": "core",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["leg raises", "hanging leg raises", "hanging knee raise", "toes to bar"],
    },
    {
        "canonical_name": "Ab Wheel Rollout",
        "slug": "ab-wheel-rollout",
        "category": "bodyweight",
        "primary_muscle_group": "core",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["ab rollout", "ab wheel", "rollouts", "ab wheel rollouts"],
    },
    {
        "canonical_name": "Bodyweight Lunge",
        "slug": "bodyweight-lunge",
        "category": "bodyweight",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["lunges", "bodyweight lunges", "air lunges", "bodyweight lunge"],
    },
    {
        "canonical_name": "Bodyweight Squat",
        "slug": "bodyweight-squat",
        "category": "bodyweight",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["air squat", "air squats", "bodyweight squats", "bodyweight squat"],
    },
    {
        "canonical_name": "Box Jump",
        "slug": "box-jump",
        "category": "bodyweight",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["box jump", "box jumps"],
    },
    {
        "canonical_name": "Burpee",
        "slug": "burpee",
        "category": "bodyweight",
        "primary_muscle_group": "full_body",
        "is_bodyweight": True,
        "default_unit": "lbs",
        "aliases": ["burpee", "burpees"],
    },

    # --- Machine & Cable ---
    {
        "canonical_name": "Lat Pulldown",
        "slug": "lat-pulldown",
        "category": "cable",
        "primary_muscle_group": "back",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["lat pulldowns", "pulldown", "pulldowns", "cable pulldown", "lat pulldown"],
    },
    {
        "canonical_name": "Seated Cable Row",
        "slug": "seated-cable-row",
        "category": "cable",
        "primary_muscle_group": "back",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["cable row", "cable rows", "low row", "seated row", "seated cable rows"],
    },
    {
        "canonical_name": "Cable Tricep Pushdown",
        "slug": "cable-tricep-pushdown",
        "category": "cable",
        "primary_muscle_group": "arms",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["tricep pushdown", "tricep pushdowns", "rope pushdown", "cable pushdown", "tricep pressdown"],
    },
    {
        "canonical_name": "Cable Bicep Curl",
        "slug": "cable-bicep-curl",
        "category": "cable",
        "primary_muscle_group": "arms",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["cable curls", "cable curl", "cable bicep curls"],
    },
    {
        "canonical_name": "Cable Face Pull",
        "slug": "cable-face-pull",
        "category": "cable",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["face pull", "face pulls", "rope face pull", "cable face pulls"],
    },
    {
        "canonical_name": "Cable Lateral Raise",
        "slug": "cable-lateral-raise",
        "category": "cable",
        "primary_muscle_group": "shoulders",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["cable lateral raises", "cable side raise", "cable lateral raise"],
    },
    {
        "canonical_name": "Leg Press",
        "slug": "leg-press",
        "category": "machine",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["leg press", "leg presses", "45 degree leg press", "machine leg press"],
    },
    {
        "canonical_name": "Leg Extension",
        "slug": "leg-extension",
        "category": "machine",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["leg extension", "leg extensions", "quad extension", "machine leg extension"],
    },
    {
        "canonical_name": "Leg Curl",
        "slug": "leg-curl",
        "category": "machine",
        "primary_muscle_group": "hamstrings",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["leg curl", "leg curls", "hamstring curl", "lying leg curl", "seated leg curl"],
    },
    {
        "canonical_name": "Calf Raise",
        "slug": "calf-raise",
        "category": "machine",
        "primary_muscle_group": "calves",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["calf raises", "standing calf raise", "seated calf raise", "calf raise", "machine calf raise"],
    },
    {
        "canonical_name": "Chest Press Machine",
        "slug": "chest-press-machine",
        "category": "machine",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["machine chest press", "chest machine", "chest press machine"],
    },
    {
        "canonical_name": "Pec Deck Fly",
        "slug": "pec-deck-fly",
        "category": "machine",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["pec deck", "chest fly machine", "butterfly machine", "machine flyes"],
    },
    {
        "canonical_name": "Cable Crossover",
        "slug": "cable-crossover",
        "category": "cable",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["cable flyes", "cable fly", "cable chest fly", "cable crossover"],
    },
    {
        "canonical_name": "Smith Machine Squat",
        "slug": "smith-machine-squat",
        "category": "machine",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["smith squat", "smith machine squats"],
    },
    {
        "canonical_name": "Smith Machine Bench Press",
        "slug": "smith-machine-bench-press",
        "category": "machine",
        "primary_muscle_group": "chest",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["smith bench", "smith machine bench", "smith press"],
    },
    {
        "canonical_name": "Hack Squat",
        "slug": "hack-squat",
        "category": "machine",
        "primary_muscle_group": "quadriceps",
        "is_bodyweight": False,
        "default_unit": "lbs",
        "aliases": ["hack squat", "hack squats", "machine hack squat"],
    },
]


def exercise_uuid_for_slug(slug: str) -> uuid.UUID:
    """Return the canonical deterministic UUIDv5 for a strength exercise slug."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"coach3.exercise.{slug}")


async def seed_exercises(session: AsyncSession) -> int:
    """Seeds exercise definitions and aliases idempotently using deterministic UUIDv5 IDs."""
    created_count = 0

    for defn in EXERCISE_DEFINITIONS:
        q = select(StrengthExercise).where(StrengthExercise.slug == defn["slug"])
        res = await session.execute(q)
        exercise = res.scalar_one_or_none()

        if not exercise:
            exercise = StrengthExercise(
                id=exercise_uuid_for_slug(defn["slug"]),
                canonical_name=defn["canonical_name"],
                slug=defn["slug"],
                category=defn["category"],
                primary_muscle_group=defn["primary_muscle_group"],
                is_bodyweight=defn["is_bodyweight"],
                default_unit=defn["default_unit"],
            )
            session.add(exercise)
            await session.flush()
            created_count += 1
            existing_aliases: set[str] = set()
        else:
            alias_res = await session.execute(
                select(ExerciseAlias.alias).where(ExerciseAlias.exercise_id == exercise.id)
            )
            existing_aliases = {a.lower() for a in alias_res.scalars().all()}

        # Seed aliases without triggering async lazy loads
        for alias_str in defn["aliases"]:
            alias_lower = alias_str.strip().lower()
            if alias_lower not in existing_aliases:
                alias_obj = ExerciseAlias(
                    id=uuid.uuid4(),
                    exercise_id=exercise.id,
                    alias=alias_lower,
                )
                session.add(alias_obj)
                existing_aliases.add(alias_lower)

    await session.flush()
    return created_count


async def main():
    async with async_session_factory() as session:
        count = await seed_exercises(session)
        await session.commit()
        print(f"Seeded {count} exercises successfully.")


if __name__ == "__main__":
    asyncio.run(main())

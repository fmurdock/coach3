"""Philosophy Management Service (Constitution Principle V).

Handles CRUD, seeding standard coaching presets, activating philosophies,
and managing manual athlete context notes.
"""

from typing import List
import uuid

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.coaching import CoachingPhilosophy
from src.schemas.coaching import SavePhilosophyRequest

DEFAULT_PHILOSOPHIES = [
    {
        "name": "Polarized 80/20",
        "description": "Stephen Seiler's polarized model: 80% low-intensity Zone 2 base volume, 20% high-intensity interval / strength work.",
        "target_zone2_pct": 80.0,
        "max_weekly_volume_ramp_pct": 10.0,
        "max_rpe_threshold": 8.5,
        "min_rest_days_per_week": 2,
        "primary_modality": "hybrid",
        "custom_context_notes": None,
    },
    {
        "name": "Norwegian Method",
        "description": "Double threshold training with extensive sub-threshold lactate control and high aerobic volume.",
        "target_zone2_pct": 85.0,
        "max_weekly_volume_ramp_pct": 8.0,
        "max_rpe_threshold": 8.0,
        "min_rest_days_per_week": 1,
        "primary_modality": "endurance",
        "custom_context_notes": None,
    },
    {
        "name": "Pyramidal",
        "description": "Classic pyramid distribution with moderate Zone 2, noticeable tempo/sweetspot Zone 3 work, and low sprint volume.",
        "target_zone2_pct": 70.0,
        "max_weekly_volume_ramp_pct": 10.0,
        "max_rpe_threshold": 9.0,
        "min_rest_days_per_week": 2,
        "primary_modality": "hybrid",
        "custom_context_notes": None,
    },
    {
        "name": "Concurrent Strength-Endurance",
        "description": "Balanced hypertrophy and strength progression alongside maintenance aerobic base work.",
        "target_zone2_pct": 75.0,
        "max_weekly_volume_ramp_pct": 10.0,
        "max_rpe_threshold": 9.0,
        "min_rest_days_per_week": 2,
        "primary_modality": "strength",
        "custom_context_notes": None,
    },
]


class PhilosophyService:
    @classmethod
    async def seed_defaults(cls, session: AsyncSession, user_id: uuid.UUID) -> None:
        """Seeds standard philosophies for user if none exist."""
        stmt = (
            select(CoachingPhilosophy)
            .where(CoachingPhilosophy.user_id == user_id)
            .limit(1)
        )
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is not None:
            return

        for i, preset in enumerate(DEFAULT_PHILOSOPHIES):
            phil = CoachingPhilosophy(
                id=uuid.uuid4(),
                user_id=user_id,
                name=preset["name"],
                description=preset["description"],
                target_zone2_pct=preset["target_zone2_pct"],
                max_weekly_volume_ramp_pct=preset["max_weekly_volume_ramp_pct"],
                max_rpe_threshold=preset["max_rpe_threshold"],
                min_rest_days_per_week=preset["min_rest_days_per_week"],
                primary_modality=preset["primary_modality"],
                custom_context_notes=preset["custom_context_notes"],
                is_active=(i == 0),  # First preset active by default
            )
            session.add(phil)
        await session.flush()

    @classmethod
    async def list_philosophies(
        cls, session: AsyncSession, user_id: uuid.UUID
    ) -> List[CoachingPhilosophy]:
        """Lists all philosophies for a user, seeding defaults if needed."""
        await cls.seed_defaults(session, user_id)
        stmt = (
            select(CoachingPhilosophy)
            .where(CoachingPhilosophy.user_id == user_id)
            .order_by(CoachingPhilosophy.created_at.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def save_philosophy(
        cls, session: AsyncSession, user_id: uuid.UUID, data: SavePhilosophyRequest
    ) -> CoachingPhilosophy:
        """Creates or updates a philosophy."""
        stmt = select(CoachingPhilosophy).where(
            and_(
                CoachingPhilosophy.user_id == user_id,
                CoachingPhilosophy.name == data.name,
            )
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            if data.description is not None:
                existing.description = data.description
            existing.target_zone2_pct = data.target_zone2_pct
            existing.max_weekly_volume_ramp_pct = data.max_weekly_volume_ramp_pct
            existing.max_rpe_threshold = data.max_rpe_threshold
            existing.min_rest_days_per_week = data.min_rest_days_per_week
            existing.primary_modality = data.primary_modality
            existing.custom_context_notes = data.custom_context_notes
            await session.flush()
            await session.refresh(existing)
            return existing

        phil = CoachingPhilosophy(
            id=uuid.uuid4(),
            user_id=user_id,
            name=data.name,
            description=data.description,
            target_zone2_pct=data.target_zone2_pct,
            max_weekly_volume_ramp_pct=data.max_weekly_volume_ramp_pct,
            max_rpe_threshold=data.max_rpe_threshold,
            min_rest_days_per_week=data.min_rest_days_per_week,
            primary_modality=data.primary_modality,
            custom_context_notes=data.custom_context_notes,
            is_active=False,
        )
        session.add(phil)
        await session.flush()
        await session.refresh(phil)
        return phil

    @classmethod
    async def activate_philosophy(
        cls, session: AsyncSession, user_id: uuid.UUID, philosophy_id: uuid.UUID
    ) -> CoachingPhilosophy:
        """Sets a philosophy as active and deactivates all others for user."""
        stmt = select(CoachingPhilosophy).where(
            and_(
                CoachingPhilosophy.id == philosophy_id,
                CoachingPhilosophy.user_id == user_id,
            )
        )
        res = await session.execute(stmt)
        phil = res.scalar_one_or_none()
        if not phil:
            raise ValueError(f"Philosophy {philosophy_id} not found.")

        await session.execute(
            update(CoachingPhilosophy)
            .where(CoachingPhilosophy.user_id == user_id)
            .values(is_active=False)
        )

        phil.is_active = True
        await session.flush()
        await session.refresh(phil)
        return phil

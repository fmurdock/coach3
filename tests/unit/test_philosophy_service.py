"""Unit tests for PhilosophyService (CRUD, Seeding, Custom Rule Steering)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.coaching import SavePhilosophyRequest
from src.services.philosophy_service import PhilosophyService


@pytest.mark.asyncio
async def test_philosophy_seeding_and_listing(db_session: AsyncSession, sample_user):
    user, _ = sample_user

    philosophies = await PhilosophyService.list_philosophies(db_session, user.id)
    assert len(philosophies) == 4

    names = [p.name for p in philosophies]
    assert "Polarized 80/20" in names
    assert "Norwegian Method" in names
    assert "Pyramidal" in names
    assert "Concurrent Strength-Endurance" in names

    # The first one should be active
    active = [p for p in philosophies if p.is_active]
    assert len(active) == 1
    assert active[0].name == "Polarized 80/20"


@pytest.mark.asyncio
async def test_philosophy_save_and_custom_notes(db_session: AsyncSession, sample_user):
    user, _ = sample_user

    req = SavePhilosophyRequest(
        name="Custom Longevity Hybrid",
        description="Focus on VO2 max and joint health",
        target_zone2_pct=85.0,
        max_weekly_volume_ramp_pct=8.0,
        max_rpe_threshold=8.0,
        min_rest_days_per_week=2,
        primary_modality="hybrid",
        custom_context_notes="Athlete is recovering from left knee patellar tendinopathy. Strictly avoid jump squats.",
    )

    saved = await PhilosophyService.save_philosophy(db_session, user.id, req)
    assert saved.name == "Custom Longevity Hybrid"
    assert saved.target_zone2_pct == 85.0
    assert "avoid jump squats" in saved.custom_context_notes

    # Update existing
    req_update = SavePhilosophyRequest(
        name="Custom Longevity Hybrid",
        description="Updated description",
        target_zone2_pct=82.0,
        max_weekly_volume_ramp_pct=10.0,
        max_rpe_threshold=8.5,
        min_rest_days_per_week=2,
        primary_modality="hybrid",
        custom_context_notes="Updated notes: knee is feeling better.",
    )
    updated = await PhilosophyService.save_philosophy(db_session, user.id, req_update)
    assert updated.id == saved.id
    assert updated.target_zone2_pct == 82.0
    assert updated.custom_context_notes == "Updated notes: knee is feeling better."


@pytest.mark.asyncio
async def test_philosophy_activation(db_session: AsyncSession, sample_user):
    user, _ = sample_user

    # Seed defaults
    phils = await PhilosophyService.list_philosophies(db_session, user.id)
    norwegian = next(p for p in phils if p.name == "Norwegian Method")
    assert not norwegian.is_active

    # Activate Norwegian Method
    activated = await PhilosophyService.activate_philosophy(db_session, user.id, norwegian.id)
    assert activated.is_active

    # Refresh list and ensure only Norwegian is active
    phils_after = await PhilosophyService.list_philosophies(db_session, user.id)
    active_phils = [p for p in phils_after if p.is_active]
    assert len(active_phils) == 1
    assert active_phils[0].id == norwegian.id

"""Unit tests for ExerciseCatalogService taxonomy and fuzzy alias matching."""

import pytest
from src.services.exercise_catalog import ExerciseCatalogService


@pytest.fixture
def catalog():
    svc = ExerciseCatalogService()
    svc.initialize_from_definitions()
    return svc


def test_exact_alias_match(catalog):
    entry, score, alts = catalog.find_match("back squat")
    assert entry is not None
    assert entry.canonical_name == "Barbell Back Squat"
    assert entry.slug == "barbell-back-squat"
    assert score == 100.0


def test_slang_alias_bench(catalog):
    entry, score, alts = catalog.find_match("bench")
    assert entry is not None
    assert entry.canonical_name == "Barbell Bench Press"
    assert score == 100.0


def test_slang_alias_ohp(catalog):
    entry, score, alts = catalog.find_match("ohp")
    assert entry is not None
    assert entry.canonical_name == "Barbell Overhead Press"
    assert score == 100.0


def test_slang_alias_rdl(catalog):
    entry, score, alts = catalog.find_match("rdl")
    assert entry is not None
    assert entry.canonical_name == "Romanian Deadlift"
    assert score == 100.0


def test_fuzzy_match_with_typo(catalog):
    # Typo: "skwats" or "back squaat"
    entry, score, alts = catalog.find_match("back squaat", min_score=75.0)
    assert entry is not None
    assert entry.canonical_name == "Barbell Back Squat"
    assert score >= 80.0


def test_bodyweight_exercise_flag(catalog):
    entry, score, alts = catalog.find_match("pullups")
    assert entry is not None
    assert entry.canonical_name == "Pull-Up"
    assert entry.is_bodyweight is True

    dip_entry, _, _ = catalog.find_match("dips")
    assert dip_entry is not None
    assert dip_entry.is_bodyweight is True


def test_unrecognized_exercise_below_threshold(catalog):
    entry, score, alts = catalog.find_match("underwater basket weaving", min_score=75.0)
    assert entry is None
    assert score < 75.0
    assert len(alts) > 0  # Should provide top alternatives

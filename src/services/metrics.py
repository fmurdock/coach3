"""Canonical shared athletic metric formulas and unit conversions."""

KG_TO_LBS: float = 2.20462
KM_TO_MILES: float = 0.621371


def calculate_epley_1rm(weight: float, reps: int) -> float | None:
    """Estimate 1RM using the canonical Epley formula w * (1 + r / 30).

    Strictly capped to 1 <= reps <= 10 (sets > 10 reps measure muscular endurance, not 1RM).
    Returns None when weight <= 0, reps <= 0, or reps > 10.
    """
    if weight <= 0 or reps <= 0 or reps > 10:
        return None
    if reps == 1:
        return round(float(weight), 2)
    return round(float(weight) * (1.0 + float(reps) / 30.0), 2)


def calculate_estimated_5rm(estimated_1rm: float | None) -> float | None:
    """Estimate 5RM from estimated 1RM (1RM / 1.1667)."""
    if not estimated_1rm or estimated_1rm <= 0:
        return None
    return round(float(estimated_1rm) / 1.1667, 2)

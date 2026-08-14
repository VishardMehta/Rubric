"""Band computation and weighted aggregation.

Bands are computed here, server side, and returned with every score. The
frontend never derives a band from a number: thresholds change, and
frontend logic that duplicates them drifts until the two disagree in front
of a client (design-system.md section 3).
"""

from __future__ import annotations

from typing import Literal

from app.core.heuristics import (
    BAND_BORDERLINE_MIN,
    BAND_STRONG_MIN,
    EVAL_COMMUNICATION_WEIGHT,
    EVAL_EXPERIENCE_WEIGHT,
    EVAL_TECHNICAL_WEIGHT,
)

Band = Literal["strong", "borderline", "weak"]


def band_for(score: int) -> Band:
    """Map a 0 to 100 score onto its band."""
    if score >= BAND_STRONG_MIN:
        return "strong"
    if score >= BAND_BORDERLINE_MIN:
        return "borderline"
    return "weak"


def weighted_overall(
    technical: int,
    communication: int,
    experience: int,
) -> int:
    """The overall interview score. backend.md 5.5."""
    return round(
        technical * EVAL_TECHNICAL_WEIGHT
        + communication * EVAL_COMMUNICATION_WEIGHT
        + experience * EVAL_EXPERIENCE_WEIGHT
    )

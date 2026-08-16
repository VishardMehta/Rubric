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
    SCREENING_RESUME_WEIGHT,
    SCREENING_VOICE_WEIGHT,
)

# A silent drift here would change every candidate's score without anything
# failing, so it is checked at import rather than trusted.
assert abs(SCREENING_RESUME_WEIGHT + SCREENING_VOICE_WEIGHT - 1.0) < 1e-9

Band = Literal["strong", "borderline", "weak"]


def band_for(score: int) -> Band:
    """Map a 0 to 100 score onto its band."""
    if score >= BAND_STRONG_MIN:
        return "strong"
    if score >= BAND_BORDERLINE_MIN:
        return "borderline"
    return "weak"


def weighted_screening(resume_score: int, voice_score: int) -> int:
    """The final screening score from its two 0-100 components.

    The single place this arithmetic exists. Every caller that stores,
    ranks, bands or displays a screening score reads the result of this,
    so the weighting cannot be applied in one place and forgotten in
    another.

    The components stay on the row alongside it, because "72 overall" is
    not explainable without "81 on the resume, 58 on the introduction".
    """
    return round(
        resume_score * SCREENING_RESUME_WEIGHT + voice_score * SCREENING_VOICE_WEIGHT
    )


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

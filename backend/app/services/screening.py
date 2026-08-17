"""Stage 2: score one candidate against the rubric. backend.md 5.2.

Kept separate from the /apply route so it can be exercised without a
database, which is what the consistency harness does.
"""

from __future__ import annotations

from app.core.heuristics import SCREENING_MAX_RETRIES
from app.integrations.llm import generate_structured
from app.models import Rubric, Screening
from app.services.prompts import render_rubric_block, screening_prompts
from app.services.validation import validate_screening


def rubric_block(rubric: Rubric) -> str:
    return render_rubric_block(
        [(c.id, c.name, c.description, c.points) for c in rubric.criteria]
    )


def screen_candidate(
    rubric: Rubric,
    transcript: str,
    resume_text: str,
    declared_skills: list[str],
) -> Screening:
    """Score both sources against the rubric in a single call.

    Raises SchemaValidationFailed if the model cannot produce a result that
    passes validation within the retry budget. Nothing is repaired here: a
    total quietly corrected in Python would no longer match the reasoning
    that produced it.
    """
    system, user = screening_prompts(
        rubric_block(rubric), transcript, resume_text, declared_skills
    )

    return generate_structured(
        system,
        user,
        Screening,
        validate=lambda result: validate_screening(
            result, rubric, transcript, resume_text
        ),
        max_retries=SCREENING_MAX_RETRIES,
    )

"""Rubric fixtures. Hand written, not model generated, so the tests assert
against a known-good shape rather than against whatever a model happened to
return on the day."""

from __future__ import annotations

from app.models import Criterion, Rubric


def valid_rubric() -> Rubric:
    """Five criteria, points totalling exactly 100."""
    return Rubric(
        criteria=[
            Criterion(
                id="python_and_django",
                name="Python and Django",
                description=(
                    "Production experience with Python web frameworks. Look for "
                    "named frameworks, ORM and migration work, and testing practice."
                ),
                points=25,
                dimension="technical",
            ),
            Criterion(
                id="sql_and_data_modelling",
                name="SQL and data modelling",
                description=(
                    "Schema design and query performance. Look for indexing, "
                    "query optimisation, and relational data at scale."
                ),
                points=20,
                dimension="technical",
            ),
            Criterion(
                id="system_design",
                name="System design",
                description=(
                    "Designing services that hold up under load. Look for "
                    "described tradeoffs, caching, and failure handling."
                ),
                points=20,
                dimension="technical",
            ),
            Criterion(
                id="technical_communication",
                name="Technical communication",
                description=(
                    "Explaining technical work clearly. Look for structured "
                    "answers that name the problem, the approach and the outcome."
                ),
                points=20,
                dimension="communication",
            ),
            Criterion(
                id="relevant_experience",
                name="Relevant experience",
                description=(
                    "Years and depth in comparable roles. Look for ownership of "
                    "shipped work rather than exposure to it."
                ),
                points=15,
                dimension="experience",
            ),
        ],
        interview_topics=[
            "Django ORM and query performance",
            "Service design tradeoffs",
            "Testing strategy",
        ],
    )

"""backend.md section 11: test_rubric_points_sum and the rest of the
stage 1 contract.

These are structural invariants only. Nothing here asserts on model prose -
see CLAUDE.md "Testing". The fixtures are hand written so a failure means
the validator changed, not that a model had an off day.
"""

from __future__ import annotations

import pytest

from app.core.heuristics import RUBRIC_TOTAL_POINTS
from app.integrations.llm import ValidationViolation
from app.models import Criterion
from app.services.validation import validate_rubric
from tests.fixtures.rubrics import valid_rubric


def test_valid_rubric_passes():
    validate_rubric(valid_rubric())


def test_rubric_points_sum():
    """The load-bearing check. Points must total exactly 100."""
    rubric = valid_rubric()
    assert rubric.total_points() == RUBRIC_TOTAL_POINTS

    rubric.criteria[0].points += 1
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    assert "101" in exc.value.message


def test_points_under_total_rejected():
    rubric = valid_rubric()
    rubric.criteria[0].points -= 5
    with pytest.raises(ValidationViolation):
        validate_rubric(rubric)


def test_violation_message_names_the_actual_total_and_breakdown():
    """The message is retry guidance sent back to the model, so it has to
    state what was wrong specifically enough to be actionable."""
    rubric = valid_rubric()
    rubric.criteria[0].points = 30
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    message = exc.value.message
    assert "105" in message
    assert "python_and_django=30" in message


def test_too_few_criteria_rejected():
    rubric = valid_rubric()
    rubric.criteria = rubric.criteria[:3]
    rubric.criteria[0].points = 60
    rubric.criteria[1].points = 20
    rubric.criteria[2].points = 20
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    assert "3 criteria" in exc.value.message


def test_too_many_criteria_rejected():
    rubric = valid_rubric()
    extra = [
        Criterion(
            id=f"extra_{i}",
            name=f"Extra {i}",
            description="Filler.",
            points=5,
            dimension="technical",
        )
        for i in range(3)
    ]
    rubric.criteria = rubric.criteria + extra
    rubric.criteria[0].points = 10
    with pytest.raises(ValidationViolation):
        validate_rubric(rubric)


@pytest.mark.parametrize(
    "bad_id",
    ["Python_Django", "python-django", "python django", "_python", "python__django", ""],
)
def test_non_slug_ids_rejected(bad_id):
    rubric = valid_rubric()
    rubric.criteria[0].id = bad_id
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    assert "slug" in exc.value.message


def test_duplicate_ids_rejected():
    rubric = valid_rubric()
    rubric.criteria[1].id = rubric.criteria[0].id
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    assert "more than once" in exc.value.message


def test_zero_point_criterion_rejected():
    rubric = valid_rubric()
    rubric.criteria[0].points = 0
    rubric.criteria[1].points += 25
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    assert "positive" in exc.value.message


def test_empty_description_rejected():
    rubric = valid_rubric()
    rubric.criteria[0].description = "   "
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    assert "description" in exc.value.message


def test_missing_interview_topics_rejected():
    rubric = valid_rubric()
    rubric.interview_topics = []
    with pytest.raises(ValidationViolation):
        validate_rubric(rubric)


def test_criterion_lookup_helpers():
    rubric = valid_rubric()
    assert rubric.by_id("system_design").name == "System design"
    assert rubric.by_id("nope") is None
    assert "system_design" in rubric.criterion_ids()

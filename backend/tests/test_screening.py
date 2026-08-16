"""Screening validation. backend.md section 11:
test_subscores_sum, test_criteria_ids_exist, test_evidence_source_matches.

Structural invariants only - no assertions on model prose. Gemini is not
called here; the live consistency harness covers that separately.
"""

from __future__ import annotations

import pytest

from app.integrations.llm import ValidationViolation
from app.models import Evidence, Screening, SubScore
from app.services.scoring import band_for, weighted_overall, weighted_screening
from app.services.validation import validate_screening
from tests.fixtures.rubrics import valid_rubric

TRANSCRIPT = (
    "I have been a backend engineer for five years, mostly Python. "
    "I built a recommendation system using collaborative filtering and "
    "handled the cold start problem with a popularity fallback. "
    "I am less experienced with distributed system design."
)
RESUME = (
    "Priya Nair\n"
    "Backend Engineer, Zoho, 2023 to present. "
    "Owned PostgreSQL schema design and query performance.\n"
    "SKILLS Python, Django, PostgreSQL, pytest"
)


def _screening(**overrides) -> Screening:
    """A valid two-component screening for the fixture rubric.

    Each component is a full scoring of the same 100-point rubric from one
    source, so every quote in `sub_scores` comes from RESUME and every
    quote in `voice_sub_scores` comes from TRANSCRIPT.
    """
    base: dict = {
        # Resume component: 15 + 18 + 0 + 0 + 12 = 45
        "sub_scores": [
            SubScore(
                criterion_id="python_and_django",
                evidence=[
                    Evidence(source="resume", quote="Python, Django, PostgreSQL, pytest")
                ],
                points_awarded=15,
                points_possible=25,
            ),
            SubScore(
                criterion_id="sql_and_data_modelling",
                evidence=[
                    Evidence(
                        source="resume",
                        quote="Owned PostgreSQL schema design and query performance",
                    )
                ],
                points_awarded=18,
                points_possible=20,
            ),
            # The resume says nothing about these two, so they score 0 with
            # no evidence rather than borrowing from the transcript.
            SubScore(
                criterion_id="system_design",
                evidence=[],
                points_awarded=0,
                points_possible=20,
            ),
            SubScore(
                criterion_id="technical_communication",
                evidence=[],
                points_awarded=0,
                points_possible=20,
            ),
            SubScore(
                criterion_id="relevant_experience",
                evidence=[
                    Evidence(
                        source="resume",
                        quote="Backend Engineer, Zoho, 2023 to present",
                    )
                ],
                points_awarded=12,
                points_possible=15,
            ),
        ],
        "total_score": 45,
        # Voice component: 20 + 0 + 5 + 15 + 12 = 52
        "voice_sub_scores": [
            SubScore(
                criterion_id="python_and_django",
                evidence=[Evidence(source="introduction", quote="mostly Python")],
                points_awarded=20,
                points_possible=25,
            ),
            SubScore(
                criterion_id="sql_and_data_modelling",
                evidence=[],
                points_awarded=0,
                points_possible=20,
            ),
            SubScore(
                criterion_id="system_design",
                evidence=[
                    Evidence(
                        source="introduction",
                        quote="I am less experienced with distributed system design",
                    )
                ],
                points_awarded=5,
                points_possible=20,
            ),
            SubScore(
                criterion_id="technical_communication",
                evidence=[
                    Evidence(
                        source="introduction",
                        quote="handled the cold start problem with a popularity fallback",
                    )
                ],
                points_awarded=15,
                points_possible=20,
            ),
            SubScore(
                criterion_id="relevant_experience",
                evidence=[
                    Evidence(
                        source="introduction",
                        quote="backend engineer for five years",
                    )
                ],
                points_awarded=12,
                points_possible=15,
            ),
        ],
        "voice_total_score": 52,
        "matched_skills": ["Python", "PostgreSQL"],
        "unevidenced_skills": ["Kubernetes"],
        "resume_intro_conflicts": [],
        "assessment": "Strong SQL evidence on the resume. System design was thin in both.",
        "recommendation": "shortlist",
    }
    base.update(overrides)
    return Screening(**base)


def _validate(screening: Screening) -> None:
    validate_screening(screening, valid_rubric(), TRANSCRIPT, RESUME)


def test_valid_screening_passes():
    _validate(_screening())


def test_subscores_sum():
    s = _screening(total_score=46)
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "45" in exc.value.message and "46" in exc.value.message


def test_voice_subscores_sum():
    """The voice component is held to the same arithmetic as the resume
    component, not treated as a softer number beside it."""
    s = _screening(voice_total_score=60)
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "52" in exc.value.message and "60" in exc.value.message


def test_each_component_may_only_quote_its_own_source():
    """A resume component quoting the transcript is the two components
    collapsing back into one, which is what the split exists to prevent."""
    s = _screening()
    s.sub_scores[0].evidence = [
        Evidence(source="introduction", quote="mostly Python")
    ]
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "resume" in exc.value.message

    s = _screening()
    s.voice_sub_scores[0].evidence = [
        Evidence(source="resume", quote="Python, Django, PostgreSQL, pytest")
    ]
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "introduction" in exc.value.message


def test_final_score_weights_the_two_components():
    """60/40, computed in one place. 45 and 52 give 48."""
    s = _screening()
    assert weighted_screening(s.total_score, s.voice_total_score) == 48
    # A candidate strong on paper and unable to describe any of it does
    # not screen the same as one who is strong at both.
    assert weighted_screening(100, 0) == 60
    assert weighted_screening(0, 100) == 40
    assert weighted_screening(100, 100) == 100


def test_criteria_ids_exist():
    s = _screening()
    s.sub_scores[0].criterion_id = "invented_criterion"
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "invented_criterion" in exc.value.message


def test_missing_criterion_rejected():
    s = _screening()
    dropped = s.sub_scores.pop()
    s.total_score -= dropped.points_awarded
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "relevant_experience" in exc.value.message


def test_duplicate_criterion_rejected():
    """Append a duplicate rather than renaming one, so this exercises the
    duplicate check rather than the missing-criterion check."""
    s = _screening()
    s.sub_scores.append(
        SubScore(
            criterion_id="python_and_django",
            evidence=[Evidence(source="resume", quote="Python, Django")],
            points_awarded=5,
            points_possible=25,
        )
    )
    s.total_score = 50
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "more than once" in exc.value.message


def test_evidence_source_matches():
    """A quote attributed to the resume that exists only in the transcript
    means the model invented support for a score it had already chosen."""
    s = _screening()
    s.sub_scores[0].evidence = [
        Evidence(source="resume", quote="mostly Python")  # actually in the transcript
    ]
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "not in the resume" in exc.value.message
    # The message should point at the right source so the retry can fix it.
    assert "introduction" in exc.value.message


def test_fabricated_quote_rejected():
    s = _screening()
    s.voice_sub_scores[0].evidence = [
        Evidence(source="introduction", quote="I led a team of fifty engineers")
    ]
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "not in the introduction" in exc.value.message


def test_quote_matching_ignores_whitespace_and_case():
    """PDF extraction and transcription both introduce line breaks a model
    will not reproduce byte for byte. Everything else must still match."""
    s = _screening()
    s.voice_sub_scores[0].evidence = [
        Evidence(source="introduction", quote="Mostly    Python")
    ]
    _validate(s)


def test_elided_quote_accepted_when_every_fragment_is_real():
    """Models habitually stitch passages with an ellipsis. Each fragment
    still has to be verbatim, so grounding holds."""
    s = _screening()
    s.voice_sub_scores[0].evidence = [
        Evidence(
            source="introduction",
            quote="I have been a backend engineer ... handled the cold start problem",
        )
    ]
    _validate(s)


def test_elided_quote_rejected_when_a_fragment_is_invented():
    s = _screening()
    s.voice_sub_scores[0].evidence = [
        Evidence(
            source="introduction",
            quote="I have been a backend engineer ... and won a Nobel prize",
        )
    ]
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "nobel" in exc.value.message.lower()


def test_points_above_possible_rejected():
    s = _screening()
    s.sub_scores[0].points_awarded = 99
    s.total_score = 149
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "outside the range" in exc.value.message


def test_points_possible_must_match_rubric():
    s = _screening()
    s.sub_scores[0].points_possible = 40
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "rubric says 25" in exc.value.message


def test_points_without_evidence_rejected():
    s = _screening()
    s.sub_scores[0].evidence = []
    with pytest.raises(ValidationViolation) as exc:
        _validate(s)
    assert "no evidence" in exc.value.message


def test_zero_points_may_have_no_evidence():
    """Scoring 0 because the sources said nothing is legitimate and must
    not be forced to invent a quote."""
    s = _screening()
    # Resume component was 45 with 15 on this criterion.
    s.sub_scores[0].evidence = []
    s.sub_scores[0].points_awarded = 0
    s.total_score = 30
    _validate(s)


def test_empty_assessment_rejected():
    s = _screening(assessment="  ")
    with pytest.raises(ValidationViolation):
        _validate(s)


def test_conflicts_do_not_affect_validation():
    """Conflicts are reported to HR as neutral observations and carry no
    score penalty (backend.md 5.2)."""
    s = _screening(
        resume_intro_conflicts=[
            "The resume lists 2023 to present at Zoho, the introduction said three years."
        ]
    )
    _validate(s)


# --- scoring.py ---------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [(0, "weak"), (44, "weak"), (45, "borderline"), (69, "borderline"),
     (70, "strong"), (100, "strong")],
)
def test_band_boundaries(score, expected):
    assert band_for(score) == expected


def test_weighted_overall():
    # technical 0.5, communication 0.25, experience 0.25
    assert weighted_overall(80, 80, 80) == 80
    assert weighted_overall(100, 0, 0) == 50
    assert weighted_overall(74, 85, 76) == round(74 * 0.5 + 85 * 0.25 + 76 * 0.25)

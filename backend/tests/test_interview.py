"""Interview engine. backend.md section 11:
test_plan_covers_rubric, test_no_repeat_questions,
test_state_object_grows_correctly.

Structural invariants only. Gemini is not called; the live run covers that.
"""

from __future__ import annotations

import pytest

from app.core.heuristics import (
    PLAN_FIXED_OPENING_SLOTS,
    PLAN_MAX_QUESTIONS,
    PLAN_MIN_QUESTIONS,
    PLAN_MIN_SLOT_FOR_DEEP_DEPTH,
    QUESTION_SIMILARITY_THRESHOLD,
    STATE_CLAIMS_MADE_CAP,
)
from app.integrations.llm import ValidationViolation
from app.models import (
    AnswerAnalysis,
    AnswerScore,
    Criterion,
    Evaluation,
    InterviewPlan,
    PlannedQuestion,
    Rubric,
    TurnResult,
)
from app.services.interview import (
    InterviewState,
    dimension_scores,
    new_token,
    planned_question_count,
)
from app.services.similarity import similarity
from app.services.validation import (
    validate_evaluation,
    validate_plan,
    validate_rubric,
    validate_turn,
)
from tests.fixtures.rubrics import valid_rubric


def _plan(rubric: Rubric, total: int | None = None) -> InterviewPlan:
    """A valid plan: three openers, then one slot per criterion."""
    total = total or planned_question_count(rubric)
    questions = [
        PlannedQuestion(
            slot=1, intent="Background", criterion_ids=["relevant_experience"], depth="opening"
        ),
        PlannedQuestion(
            slot=2, intent="A project", criterion_ids=["python_and_django"], depth="opening"
        ),
        PlannedQuestion(
            slot=3,
            intent="Their contribution",
            criterion_ids=["technical_communication"],
            depth="opening",
        ),
    ]
    remaining = [
        c.id
        for c in rubric.criteria
        if c.id not in {"relevant_experience", "python_and_django", "technical_communication"}
    ]
    slot = 4
    for criterion_id in remaining:
        questions.append(
            PlannedQuestion(
                slot=slot, intent=f"Probe {criterion_id}", criterion_ids=[criterion_id],
                depth="probing",
            )
        )
        slot += 1
    while slot <= total:
        questions.append(
            PlannedQuestion(
                slot=slot, intent="Go deeper", criterion_ids=["system_design"], depth="deep"
            )
        )
        slot += 1
    return InterviewPlan(questions=questions)


# --- plan ---------------------------------------------------------------


def test_question_count_scales_with_rubric_breadth():
    """backend.md 5.3: 4 criteria gives 6 questions, 7 gives 9."""
    def rubric_with(n: int) -> Rubric:
        base = valid_rubric()
        base.criteria = base.criteria[:1] * n
        return base

    assert planned_question_count(rubric_with(4)) == 6
    assert planned_question_count(rubric_with(7)) == 9
    # Clamped at both ends.
    assert planned_question_count(rubric_with(1)) == PLAN_MIN_QUESTIONS
    assert planned_question_count(rubric_with(20)) == PLAN_MAX_QUESTIONS


def test_plan_covers_rubric():
    rubric = valid_rubric()
    total = planned_question_count(rubric)
    validate_plan(_plan(rubric), rubric, total)


def test_plan_missing_a_criterion_rejected():
    """A criterion never probed can never be scored in the interview."""
    rubric = valid_rubric()
    total = planned_question_count(rubric)
    plan = _plan(rubric)
    for question in plan.questions:
        if "sql_and_data_modelling" in question.criterion_ids:
            question.criterion_ids = ["system_design"]
    with pytest.raises(ValidationViolation) as exc:
        validate_plan(plan, rubric, total)
    assert "sql_and_data_modelling" in exc.value.message


def test_plan_wrong_slot_count_rejected():
    rubric = valid_rubric()
    plan = _plan(rubric)
    plan.questions.pop()
    with pytest.raises(ValidationViolation):
        validate_plan(plan, rubric, planned_question_count(rubric))


def test_plan_openers_must_be_opening_depth():
    rubric = valid_rubric()
    plan = _plan(rubric)
    plan.questions[1].depth = "probing"
    with pytest.raises(ValidationViolation) as exc:
        validate_plan(plan, rubric, planned_question_count(rubric))
    assert "opening" in exc.value.message


def test_plan_no_deep_before_settling_in():
    """A candidate needs a few questions to settle before being pushed.

    With the current constants the opener rule (slots 1 to 3 must be
    'opening') already covers every slot below PLAN_MIN_SLOT_FOR_DEEP_DEPTH,
    so the dedicated deep check is defence in depth for if those constants
    diverge. This asserts the behaviour that matters - an early 'deep' is
    rejected - without pinning which rule catches it.
    """
    assert PLAN_MIN_SLOT_FOR_DEEP_DEPTH <= PLAN_FIXED_OPENING_SLOTS + 1

    rubric = valid_rubric()
    plan = _plan(rubric)
    plan.questions[PLAN_FIXED_OPENING_SLOTS - 1].depth = "deep"
    with pytest.raises(ValidationViolation):
        validate_plan(plan, rubric, planned_question_count(rubric))


def test_plan_depth_may_not_go_backwards():
    rubric = valid_rubric()
    plan = _plan(rubric)
    plan.questions[3].depth = "deep"
    plan.questions[4].depth = "probing"
    with pytest.raises(ValidationViolation) as exc:
        validate_plan(plan, rubric, planned_question_count(rubric))
    assert "backwards" in exc.value.message


def test_plan_unknown_criterion_rejected():
    rubric = valid_rubric()
    plan = _plan(rubric)
    plan.questions[3].criterion_ids = ["invented"]
    with pytest.raises(ValidationViolation) as exc:
        validate_plan(plan, rubric, planned_question_count(rubric))
    assert "invented" in exc.value.message


# --- rubric dimensions --------------------------------------------------


def test_rubric_must_cover_all_three_dimensions():
    """Every rubric must support the three reported sub-scores, otherwise
    a whole column reads 0 for every candidate on that job."""
    rubric = valid_rubric()
    for criterion in rubric.criteria:
        criterion.dimension = "technical"
    with pytest.raises(ValidationViolation) as exc:
        validate_rubric(rubric)
    assert "communication" in exc.value.message
    assert "experience" in exc.value.message


# --- similarity and repeats ---------------------------------------------


def test_similarity_ignores_filler_words():
    a = "Can you tell me about how you handled the cold start problem?"
    b = "How did you handle the cold start problem?"
    # >= because that is the comparison the validator itself uses; these two
    # land exactly on the threshold, which is the case worth pinning.
    assert similarity(a, b) >= QUESTION_SIMILARITY_THRESHOLD


def test_similarity_separates_different_topics():
    a = "How did you handle the cold start problem in that recommender?"
    b = "What testing practices did your team follow for the payments service?"
    assert similarity(a, b) < QUESTION_SIMILARITY_THRESHOLD


def _turn_result(question: str) -> TurnResult:
    return TurnResult(
        answer_scores=[
            AnswerScore(
                criterion_id="python_and_django",
                evidence="I built Django services",
                points_awarded=10,
                points_possible=25,
            )
        ],
        topics_identified=["django"],
        claims_made=["Built Django services"],
        next_question=question,
        targets_criterion_ids=["system_design"],
    )


def test_no_repeat_questions():
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    state.record_question(1, "How did you handle the cold start problem?", ["system_design"])

    repeat = _turn_result("Can you tell me how you handled the cold start problem?")
    with pytest.raises(ValidationViolation) as exc:
        validate_turn(repeat, rubric, None, state, None)
    assert "repeats" in exc.value.message
    # The message must give the model something to do instead.
    assert "not yet probed" in exc.value.message


def test_distinct_question_accepted():
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    state.record_question(1, "How did you handle the cold start problem?", ["system_design"])

    fresh = _turn_result("What did your test suite cover on the payments service?")
    validate_turn(fresh, rubric, None, state, None)


def test_turn_points_without_evidence_rejected():
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    result = _turn_result("Something entirely different about deployment pipelines")
    result.answer_scores[0].evidence = "  "
    with pytest.raises(ValidationViolation) as exc:
        validate_turn(result, rubric, None, state, None)
    assert "no evidence" in exc.value.message


def test_final_turn_needs_no_question():
    """The last turn scores only. AnswerAnalysis has no question fields, so
    validation must not demand one."""
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    analysis = AnswerAnalysis(
        answer_scores=[
            AnswerScore(
                criterion_id="system_design",
                evidence="we sharded by tenant",
                points_awarded=12,
                points_possible=20,
            )
        ],
        topics_identified=["sharding"],
        claims_made=["Sharded the database by tenant"],
    )
    validate_turn(analysis, rubric, None, state, None)


# --- state object -------------------------------------------------------


def _analysis(topics: list[str], claims: list[str]) -> AnswerAnalysis:
    return AnswerAnalysis(answer_scores=[], topics_identified=topics, claims_made=claims)


def test_state_object_grows_correctly():
    """After N answers, covered and remaining must partition the criteria
    set: never overlapping, never losing one."""
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    all_ids = {c.id for c in rubric.criteria}

    assert set(state.criteria_remaining) == all_ids
    assert state.criteria_covered == []

    probed_so_far: set[str] = set()
    for index, criterion in enumerate(rubric.criteria, start=1):
        state.record_question(index, f"Question {index}", [criterion.id])
        state.record_answer(
            index, f"Answer {index}", 5, _analysis([f"topic{index}"], [f"claim{index}"]), [criterion.id]
        )
        probed_so_far.add(criterion.id)

        covered, remaining = set(state.criteria_covered), set(state.criteria_remaining)
        assert covered == probed_so_far
        assert covered | remaining == all_ids
        assert covered & remaining == set()

    assert state.criteria_remaining == []


def test_criterion_counts_as_covered_even_when_answered_badly():
    """Coverage means 'was asked about', not 'scored well'. Re-asking a
    criterion because the answer was poor would read as badgering."""
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    state.record_answer(1, "I do not know.", 2, _analysis([], []), ["system_design"])
    assert "system_design" in state.criteria_covered
    assert "system_design" not in state.criteria_remaining


def test_claims_are_capped_most_recent_first():
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    for i in range(STATE_CLAIMS_MADE_CAP + 5):
        state.record_answer(i, "x", 1, _analysis([], [f"claim{i}"]), [])

    assert len(state.claims_made) == STATE_CLAIMS_MADE_CAP
    # Most recent first.
    assert state.claims_made[0] == f"claim{STATE_CLAIMS_MADE_CAP + 4}"


def test_repeated_claim_moves_to_front_without_duplicating():
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    state.record_answer(1, "x", 1, _analysis([], ["built a recommender"]), [])
    state.record_answer(2, "y", 1, _analysis([], ["used postgres"]), [])
    state.record_answer(3, "z", 1, _analysis([], ["built a recommender"]), [])

    assert state.claims_made.count("built a recommender") == 1
    assert state.claims_made[0] == "built a recommender"


def test_depth_by_topic_counts_revisits():
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    state.record_answer(1, "x", 1, _analysis(["recommenders"], []), [])
    state.record_answer(2, "y", 1, _analysis(["recommenders"], []), [])
    state.record_answer(3, "z", 1, _analysis(["testing"], []), [])

    assert state.depth_by_topic["recommenders"] == 2
    assert state.depth_by_topic["testing"] == 1
    assert state.topics_discussed.count("recommenders") == 1


def test_state_round_trips_through_json():
    """The state lives in jsonb between requests, so it must survive a
    serialise/deserialise cycle unchanged."""
    rubric = valid_rubric()
    state = InterviewState.initial(rubric)
    state.record_question(1, "Q1", ["python_and_django"])
    state.record_answer(1, "A1", 7, _analysis(["django"], ["shipped a service"]), ["python_and_django"])

    restored = InterviewState(state.to_dict())
    assert restored.to_dict() == state.to_dict()
    assert restored.prior_questions() == ["Q1"]


# --- dimension scores ---------------------------------------------------


def test_dimension_scores_are_percentages_of_available_points():
    rubric = Rubric(
        criteria=[
            Criterion(id="a", name="A", description="d", points=40, dimension="technical"),
            Criterion(id="b", name="B", description="d", points=40, dimension="communication"),
            Criterion(id="c", name="C", description="d", points=20, dimension="experience"),
        ],
        interview_topics=["x", "y", "z"],
    )
    accumulated = [
        AnswerScore(criterion_id="a", evidence="e", points_awarded=20, points_possible=40),
        AnswerScore(criterion_id="b", evidence="e", points_awarded=40, points_possible=40),
        AnswerScore(criterion_id="c", evidence="e", points_awarded=0, points_possible=20),
    ]
    scores = dimension_scores(rubric, accumulated)
    assert scores == {"technical": 50, "communication": 100, "experience": 0}


def test_dimension_with_no_scores_does_not_divide_by_zero():
    rubric = valid_rubric()
    assert dimension_scores(rubric, []) == {
        "technical": 0,
        "communication": 0,
        "experience": 0,
    }


def test_repeated_criterion_across_turns_accumulates():
    """A criterion probed in two slots sums both, rather than the later
    turn overwriting the earlier one."""
    rubric = Rubric(
        criteria=[
            Criterion(id="a", name="A", description="d", points=10, dimension="technical"),
            Criterion(id="b", name="B", description="d", points=10, dimension="communication"),
            Criterion(id="c", name="C", description="d", points=10, dimension="experience"),
        ],
        interview_topics=["x"],
    )
    accumulated = [
        AnswerScore(criterion_id="a", evidence="e", points_awarded=5, points_possible=10),
        AnswerScore(criterion_id="a", evidence="e", points_awarded=10, points_possible=10),
    ]
    # 15 earned of 20 available.
    assert dimension_scores(rubric, accumulated)["technical"] == 75


# --- evaluation ---------------------------------------------------------


def test_evaluation_bounds():
    ok = Evaluation(
        strengths=["Explained the cold start fallback.", "Gave concrete latency numbers."],
        concerns=["Could not describe offline evaluation."],
        recommendation="shortlist",
    )
    validate_evaluation(ok)

    with pytest.raises(ValidationViolation):
        validate_evaluation(
            Evaluation(strengths=["only one"], concerns=["a"], recommendation="review")
        )
    with pytest.raises(ValidationViolation):
        validate_evaluation(
            Evaluation(strengths=["a", "b"], concerns=[], recommendation="review")
        )


def test_evaluation_rejects_empty_entries():
    with pytest.raises(ValidationViolation):
        validate_evaluation(
            Evaluation(strengths=["a", "   "], concerns=["c"], recommendation="review")
        )


# --- token --------------------------------------------------------------


def test_tokens_are_unguessable_and_unique():
    tokens = {new_token() for _ in range(200)}
    assert len(tokens) == 200
    assert all(len(t) >= 40 for t in tokens)

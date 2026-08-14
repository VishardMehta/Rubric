"""The interview engine: plan, state, turn advancement, evaluation.

This is the part that separates Rubric from a wrapper around a chat model
(product.md section 6).

The plan is generated once and fixed. It guarantees the interview covers
the whole rubric, because purely reactive questioning follows whatever the
candidate mentioned first and can spend an entire interview on one topic.

The state is rebuilt after every answer and passed into every question
generation call. It guarantees each question is specific, because a
question generated without it is generic. Together they produce "how did
you handle the cold start problem in that recommender" rather than "tell me
about your experience with system design".
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from app.core.heuristics import (
    PLAN_MAX_QUESTIONS,
    PLAN_MIN_QUESTIONS,
    STATE_CLAIMS_MADE_CAP,
    TURN_GENERATION_MAX_RETRIES,
)
from app.integrations.llm import generate_structured
from app.models import (
    AnswerAnalysis,
    AnswerScore,
    Evaluation,
    InterviewPlan,
    Rubric,
    TurnResult,
)
from app.services.prompts import (
    evaluation_prompts,
    final_turn_prompts,
    plan_prompts,
    turn_prompts,
)
from app.services.scoring import weighted_overall
from app.services.similarity import most_similar_prior, similarity
from app.services.validation import validate_evaluation, validate_plan, validate_turn

logger = logging.getLogger("rubric.interview")


def new_token() -> str:
    """An opaque, non-guessable interview token.

    token_urlsafe(32) is 256 bits of entropy. The interview URL is the only
    thing standing between a stranger and someone else's interview, so it
    is not derived from the candidate id or anything else guessable.
    """
    return secrets.token_urlsafe(32)


def planned_question_count(rubric: Rubric) -> int:
    """Total questions for this rubric.

    Three fixed openers plus roughly one slot per criterion, clamped to the
    range in heuristics.py. A 4 criterion rubric gives 6 questions, a 7
    criterion rubric gives 9 (backend.md 5.3).
    """
    return max(
        PLAN_MIN_QUESTIONS,
        min(PLAN_MAX_QUESTIONS, len(rubric.criteria) + 2),
    )


# ---------------------------------------------------------------------
# Interview state. product.md section 6
# ---------------------------------------------------------------------


class InterviewState:
    """The object carried into every question generation call.

    Stored as jsonb on interviews.state_object and rebuilt after each
    answer.
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        data = data or {}
        self.questions_asked: list[dict] = data.get("questions_asked", [])
        self.answers: list[dict] = data.get("answers", [])
        self.topics_discussed: list[str] = data.get("topics_discussed", [])
        self.claims_made: list[str] = data.get("claims_made", [])
        self.criteria_covered: list[str] = data.get("criteria_covered", [])
        self.criteria_remaining: list[str] = data.get("criteria_remaining", [])
        self.depth_by_topic: dict[str, int] = data.get("depth_by_topic", {})

    @classmethod
    def initial(cls, rubric: Rubric) -> InterviewState:
        state = cls()
        state.criteria_remaining = [c.id for c in rubric.criteria]
        return state

    def to_dict(self) -> dict[str, Any]:
        return {
            "questions_asked": self.questions_asked,
            "answers": self.answers,
            "topics_discussed": self.topics_discussed,
            "claims_made": self.claims_made,
            "criteria_covered": self.criteria_covered,
            "criteria_remaining": self.criteria_remaining,
            "depth_by_topic": self.depth_by_topic,
        }

    def record_question(self, slot: int, question: str, criterion_ids: list[str]) -> None:
        self.questions_asked.append(
            {"slot": slot, "question": question, "criterion_ids": list(criterion_ids)}
        )

    def record_answer(
        self,
        slot: int,
        transcript: str,
        response_time_seconds: int | None,
        analysis: AnswerAnalysis,
        probed_criterion_ids: list[str],
    ) -> None:
        """Fold one answered turn into the state.

        A criterion counts as covered once it has been *asked about*, not
        once it scored well. A candidate who answers badly has still been
        given their chance at it, and re-asking would read as badgering.
        """
        self.answers.append(
            {
                "slot": slot,
                "transcript": transcript,
                "response_time_seconds": response_time_seconds,
            }
        )

        for topic in analysis.topics_identified:
            if topic not in self.topics_discussed:
                self.topics_discussed.append(topic)
            self.depth_by_topic[topic] = self.depth_by_topic.get(topic, 0) + 1

        for claim in analysis.claims_made:
            if claim in self.claims_made:
                self.claims_made.remove(claim)
            self.claims_made.insert(0, claim)
        # Most recent first, capped: an unbounded state grows the prompt
        # every turn until latency becomes visible.
        del self.claims_made[STATE_CLAIMS_MADE_CAP:]

        for criterion_id in probed_criterion_ids:
            if criterion_id not in self.criteria_covered:
                self.criteria_covered.append(criterion_id)
            if criterion_id in self.criteria_remaining:
                self.criteria_remaining.remove(criterion_id)

    def prior_questions(self) -> list[str]:
        return [q["question"] for q in self.questions_asked]


# ---------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------


def generate_plan(rubric: Rubric, screening: dict[str, Any] | None) -> InterviewPlan:
    total = planned_question_count(rubric)
    system, user = plan_prompts(rubric, screening, total)
    return generate_structured(
        system,
        user,
        InterviewPlan,
        validate=lambda plan: validate_plan(plan, rubric, total),
        max_retries=TURN_GENERATION_MAX_RETRIES,
    )


# ---------------------------------------------------------------------
# Turn advancement
# ---------------------------------------------------------------------


def advance_turn(
    rubric: Rubric,
    plan: InterviewPlan,
    state: InterviewState,
    answered_slot: int,
    answer_transcript: str,
    is_final: bool,
) -> TurnResult | AnswerAnalysis:
    """Score the answer that just arrived and, unless this was the last
    slot, generate the next question.

    One call does both. Scoring fields are declared before question fields
    so the answer is assessed before the follow-up is written.
    """
    answered = plan.slot(answered_slot)
    next_slot = plan.slot(answered_slot + 1)

    if is_final or next_slot is None:
        system, user = final_turn_prompts(rubric, answered, state, answer_transcript)
        return generate_structured(
            system,
            user,
            AnswerAnalysis,
            validate=lambda result: validate_turn(result, rubric, answered, state),
            max_retries=TURN_GENERATION_MAX_RETRIES,
        )

    system, user = turn_prompts(rubric, answered, next_slot, state, answer_transcript)
    return generate_structured(
        system,
        user,
        TurnResult,
        validate=lambda result: validate_turn(result, rubric, answered, state, next_slot),
        max_retries=TURN_GENERATION_MAX_RETRIES,
    )


def opening_question() -> str:
    """The first question, asked before any answer exists.

    Fixed wording rather than generated: there is no candidate input yet to
    adapt to, so a model call here would spend quota and latency to produce
    a sentence we can write ourselves. It also guarantees every interview
    opens the same calm, predictable way.
    """
    return (
        "To start, tell me about yourself and the work you have been doing recently."
    )


# ---------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------


def dimension_scores(
    rubric: Rubric, accumulated: list[AnswerScore]
) -> dict[str, int]:
    """Technical, communication and experience scores, 0 to 100.

    Computed here, not by the model (backend.md 5.5). Each dimension is the
    percentage of available points earned across the criteria tagged with
    it. A dimension with no criteria scores 0 rather than dividing by zero,
    though rubric validation requires all three to be present.
    """
    earned: dict[str, int] = {}
    possible: dict[str, int] = {}

    for score in accumulated:
        criterion = rubric.by_id(score.criterion_id)
        if criterion is None:
            continue
        dimension = criterion.dimension
        earned[dimension] = earned.get(dimension, 0) + score.points_awarded
        possible[dimension] = possible.get(dimension, 0) + score.points_possible

    out = {}
    for dimension in ("technical", "communication", "experience"):
        available = possible.get(dimension, 0)
        out[dimension] = (
            round(100 * earned.get(dimension, 0) / available) if available else 0
        )
    return out


def evaluate_interview(
    rubric: Rubric,
    state: InterviewState,
    accumulated: list[AnswerScore],
) -> tuple[Evaluation, dict[str, int]]:
    """Aggregate the per-answer scores, then have the model write the
    narrative against those numbers.

    Because every answer was already scored as it arrived, this call
    aggregates rather than re-reading the whole transcript, which is why it
    takes seconds rather than half a minute.
    """
    dimensions = dimension_scores(rubric, accumulated)
    overall = weighted_overall(
        dimensions["technical"],
        dimensions["communication"],
        dimensions["experience"],
    )
    scores = {**dimensions, "overall": overall}

    system, user = evaluation_prompts(rubric, state, scores)
    evaluation = generate_structured(
        system,
        user,
        Evaluation,
        validate=validate_evaluation,
        max_retries=TURN_GENERATION_MAX_RETRIES,
    )
    return evaluation, scores


__all__ = [
    "InterviewState",
    "advance_turn",
    "dimension_scores",
    "evaluate_interview",
    "generate_plan",
    "most_similar_prior",
    "new_token",
    "opening_question",
    "planned_question_count",
    "similarity",
]

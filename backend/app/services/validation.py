"""Post-generation checks for every LLM stage.

Nothing here repairs output. A validator either passes or raises
ValidationViolation with a message written as retry guidance for the model.
llm.generate_structured appends that message to a single retry, and a
second failure becomes a real error.

Why not repair: a rubric quietly adjusted to sum to 100 no longer matches
the reasoning that produced it (backend.md 5.1). The same applies to every
other check here. Silent repair turns a visible failure into an invisible
wrong answer.
"""

from __future__ import annotations

import itertools
import re

from app.core.heuristics import (
    EVAL_MAX_CONCERNS,
    EVAL_MAX_STRENGTHS,
    EVAL_MIN_CONCERNS,
    EVAL_MIN_STRENGTHS,
    JOB_FACTS_MAX_SKILLS,
    JOB_FACTS_MIN_DESCRIPTION_CHARS,
    PLAN_FIXED_OPENING_SLOTS,
    PLAN_MIN_SLOT_FOR_DEEP_DEPTH,
    QUESTION_SIMILARITY_THRESHOLD,
    RESUME_PROFILE_MAX_HIGHLIGHTS,
    RESUME_PROFILE_MAX_SKILLS,
    RUBRIC_MAX_CRITERIA,
    RUBRIC_MIN_CRITERIA,
    RUBRIC_TOTAL_POINTS,
)
from app.integrations.llm import ValidationViolation
from app.models import (
    AnswerAnalysis,
    Evaluation,
    InterviewPlan,
    JobFacts,
    PlannedQuestion,
    ResumeProfile,
    Rubric,
    Screening,
    TurnResult,
)
from app.services.similarity import most_similar_prior

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
# A resume link has to be dereferenceable to be worth rendering as one.
_LINK_RE = re.compile(r"^(https?://|www\.)\S+$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
# Matches a literal ellipsis character or three or more dots, with any
# surrounding whitespace, as used to elide the middle of a quote.
_ELLIPSIS_RE = re.compile(r"\s*(?:…|\.{3,})\s*")


def _normalise(text: str) -> str:
    """Lowercase with runs of whitespace collapsed.

    Quote checking is deliberately whitespace and case insensitive.
    Transcripts and PDF extraction both introduce line breaks and spacing
    that a model will not reproduce byte for byte, and failing a correct
    quote over a newline would be a false alarm. Everything else about the
    quote still has to match.
    """
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


def validate_rubric(rubric: Rubric) -> None:
    """backend.md 5.1: 4 to 7 criteria, points total exactly 100, ids
    unique and slug shaped."""
    count = len(rubric.criteria)
    if count < RUBRIC_MIN_CRITERIA or count > RUBRIC_MAX_CRITERIA:
        raise ValidationViolation(
            f"You returned {count} criteria. Return between "
            f"{RUBRIC_MIN_CRITERIA} and {RUBRIC_MAX_CRITERIA}."
        )

    for criterion in rubric.criteria:
        if not _SLUG_RE.match(criterion.id):
            raise ValidationViolation(
                f"The criterion id {criterion.id!r} is not a valid slug. Use "
                "lowercase letters, digits and single underscores, for "
                "example python_and_django."
            )
        if criterion.points <= 0:
            raise ValidationViolation(
                f"The criterion {criterion.id!r} has {criterion.points} points. "
                "Every criterion must carry a positive whole number of points."
            )
        if not criterion.description.strip():
            raise ValidationViolation(
                f"The criterion {criterion.id!r} has an empty description. Every "
                "criterion needs scoring guidance naming the evidence that earns "
                "points."
            )

    ids = [c.id for c in rubric.criteria]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValidationViolation(
            f"These criterion ids appear more than once: {sorted(duplicates)}. "
            "Give every criterion a distinct id."
        )

    total = rubric.total_points()
    if total != RUBRIC_TOTAL_POINTS:
        breakdown = ", ".join(f"{c.id}={c.points}" for c in rubric.criteria)
        raise ValidationViolation(
            f"Your points total {total}, not {RUBRIC_TOTAL_POINTS}. You had "
            f"{breakdown}. Adjust the allocations so they add up to exactly "
            f"{RUBRIC_TOTAL_POINTS}."
        )

    if not rubric.interview_topics:
        raise ValidationViolation(
            "Return at least three interview topics worth probing in a live "
            "interview."
        )

    # The Interview Result screen always reports technical, communication
    # and experience sub-scores, and those are computed by grouping rubric
    # criteria by dimension. A rubric missing a dimension would produce a
    # permanent 0 in that column for every candidate on the job.
    missing_dimensions = sorted(
        {"technical", "communication", "experience"}
        - {c.dimension for c in rubric.criteria}
    )
    if missing_dimensions:
        raise ValidationViolation(
            f"No criterion covers these dimensions: {missing_dimensions}. Every "
            "rubric needs at least one criterion in each of technical, "
            "communication and experience, because all three are reported "
            "separately after the interview."
        )


def validate_screening(
    screening: Screening,
    rubric: Rubric,
    transcript: str,
    resume_text: str,
) -> None:
    """backend.md 5.2.

    The evidence-source check is the one that does the real work. A quote
    attributed to the resume that only exists in the transcript means the
    model invented support for a score it had already decided on, which is
    exactly the failure mode the sub-score discipline exists to prevent.
    """
    scored_ids = [s.criterion_id for s in screening.sub_scores]
    rubric_ids = rubric.criterion_ids()

    unknown = [i for i in scored_ids if i not in rubric_ids]
    if unknown:
        raise ValidationViolation(
            f"These criterion ids are not in the rubric: {sorted(set(unknown))}. "
            f"Score exactly the rubric criteria: {sorted(rubric_ids)}."
        )

    missing = sorted(rubric_ids - set(scored_ids))
    if missing:
        raise ValidationViolation(
            f"You did not score these criteria: {missing}. Return one entry per "
            "rubric criterion, scoring 0 where the sources show nothing."
        )

    duplicates = {i for i in scored_ids if scored_ids.count(i) > 1}
    if duplicates:
        raise ValidationViolation(
            f"These criteria were scored more than once: {sorted(duplicates)}. "
            "Return exactly one entry per criterion."
        )

    normalised_sources = {
        "introduction": _normalise(transcript),
        "resume": _normalise(resume_text),
    }

    for sub in screening.sub_scores:
        criterion = rubric.by_id(sub.criterion_id)
        assert criterion is not None  # guaranteed by the unknown-id check above

        if sub.points_possible != criterion.points:
            raise ValidationViolation(
                f"For {sub.criterion_id} you set points_possible to "
                f"{sub.points_possible}, but the rubric says {criterion.points}. "
                "Copy points_possible from the rubric."
            )

        if not 0 <= sub.points_awarded <= criterion.points:
            raise ValidationViolation(
                f"For {sub.criterion_id} you awarded {sub.points_awarded} points, "
                f"which is outside the range 0 to {criterion.points}."
            )

        if sub.points_awarded > 0 and not sub.evidence:
            raise ValidationViolation(
                f"You awarded {sub.points_awarded} points for {sub.criterion_id} "
                "with no evidence. Quote the span that earns the points, or "
                "award 0."
            )

        for item in sub.evidence:
            haystack = normalised_sources[item.source]
            needle = _normalise(item.quote)
            if not needle:
                raise ValidationViolation(
                    f"An evidence quote for {sub.criterion_id} is empty. Quote a "
                    "real span or remove it."
                )
            # Models habitually elide with an ellipsis when quoting across a
            # gap. Every fragment still has to appear verbatim in the named
            # source, so grounding is unchanged - this only avoids spending a
            # retry on a quote that is actually well founded.
            fragments = [f for f in (_normalise(p) for p in _ELLIPSIS_RE.split(needle)) if f]
            if len(fragments) > 1:
                missing_fragment = next(
                    (f for f in fragments if f not in haystack), None
                )
                if missing_fragment is None:
                    continue
                raise ValidationViolation(
                    f"Part of an evidence quote for {sub.criterion_id} is not in "
                    f"the {item.source}: {missing_fragment!r}. Quote one "
                    "continuous span, or add a separate evidence entry for each "
                    "passage."
                )
            if needle not in haystack:
                other = "resume" if item.source == "introduction" else "introduction"
                found_elsewhere = needle in normalised_sources[other]
                hint = (
                    f" That text appears in the {other}, not the {item.source}. "
                    f"Tag it as {other}."
                    if found_elsewhere
                    else " Copy the wording exactly as it appears in the source."
                )
                raise ValidationViolation(
                    f"The quote {item.quote!r} for {sub.criterion_id} is not in "
                    f"the {item.source}.{hint}"
                )

    total = sum(s.points_awarded for s in screening.sub_scores)
    if total != screening.total_score:
        breakdown = ", ".join(
            f"{s.criterion_id}={s.points_awarded}" for s in screening.sub_scores
        )
        raise ValidationViolation(
            f"Your sub-scores add up to {total}, but you reported a total of "
            f"{screening.total_score}. You awarded {breakdown}. Restate the "
            "total so it equals the sum."
        )

    if not screening.assessment.strip():
        raise ValidationViolation(
            "The assessment is empty. Write three to five sentences on what the "
            "evidence showed against the rubric."
        )


# ---------------------------------------------------------------------
# Stage 3: interview plan. backend.md 5.3
# ---------------------------------------------------------------------

_DEPTH_ORDER = {"opening": 0, "probing": 1, "deep": 2}


def validate_plan(plan: InterviewPlan, rubric: Rubric, total_questions: int) -> None:
    slots = [q.slot for q in plan.questions]
    expected = list(range(1, total_questions + 1))

    if sorted(slots) != expected:
        raise ValidationViolation(
            f"You returned slots {sorted(slots)}. Return exactly {total_questions} "
            f"questions numbered {expected[0]} to {expected[-1]}, each once."
        )

    ordered = sorted(plan.questions, key=lambda q: q.slot)
    rubric_ids = rubric.criterion_ids()

    for question in ordered:
        unknown = [c for c in question.criterion_ids if c not in rubric_ids]
        if unknown:
            raise ValidationViolation(
                f"Slot {question.slot} names criteria that are not in the rubric: "
                f"{unknown}. Use only these ids: {sorted(rubric_ids)}."
            )
        if not question.criterion_ids:
            raise ValidationViolation(
                f"Slot {question.slot} has no criteria attached. Every slot must "
                "probe at least one rubric criterion."
            )
        if not question.intent.strip():
            raise ValidationViolation(
                f"Slot {question.slot} has an empty intent. State in one sentence "
                "what the question is for."
            )

    for question in ordered[:PLAN_FIXED_OPENING_SLOTS]:
        if question.depth != "opening":
            raise ValidationViolation(
                f"Slot {question.slot} is one of the first {PLAN_FIXED_OPENING_SLOTS} "
                f"openers, so its depth must be 'opening', not '{question.depth}'."
            )

    for question in ordered:
        if question.depth == "deep" and question.slot < PLAN_MIN_SLOT_FOR_DEEP_DEPTH:
            raise ValidationViolation(
                f"Slot {question.slot} is marked 'deep'. Depth 'deep' may not appear "
                f"before slot {PLAN_MIN_SLOT_FOR_DEEP_DEPTH}; a candidate needs a few "
                "questions to settle first."
            )

    for previous, current in itertools.pairwise(ordered):
        if _DEPTH_ORDER[current.depth] < _DEPTH_ORDER[previous.depth]:
            raise ValidationViolation(
                f"Depth goes backwards from slot {previous.slot} ({previous.depth}) "
                f"to slot {current.slot} ({current.depth}). Depth must build, not "
                "drop back."
            )

    planned = {c for q in plan.questions for c in q.criterion_ids}
    uncovered = sorted(rubric_ids - planned)
    if uncovered:
        raise ValidationViolation(
            f"These rubric criteria are never probed: {uncovered}. Every criterion "
            "must appear in at least one slot, otherwise the interview cannot score "
            "them."
        )


# ---------------------------------------------------------------------
# Stage 4: turn result. backend.md 5.4
# ---------------------------------------------------------------------


def validate_turn(
    result: AnswerAnalysis,
    rubric: Rubric,
    answered_slot: PlannedQuestion | None,
    state,
    next_slot: PlannedQuestion | None = None,
) -> None:
    rubric_ids = rubric.criterion_ids()

    for score in result.answer_scores:
        criterion = rubric.by_id(score.criterion_id)
        if criterion is None:
            raise ValidationViolation(
                f"You scored {score.criterion_id!r}, which is not in the rubric. "
                f"Use only these ids: {sorted(rubric_ids)}."
            )
        if score.points_possible != criterion.points:
            raise ValidationViolation(
                f"For {score.criterion_id} you set points_possible to "
                f"{score.points_possible}, but the rubric says {criterion.points}."
            )
        if not 0 <= score.points_awarded <= criterion.points:
            raise ValidationViolation(
                f"For {score.criterion_id} you awarded {score.points_awarded}, "
                f"outside the range 0 to {criterion.points}."
            )
        if score.points_awarded > 0 and not score.evidence.strip():
            raise ValidationViolation(
                f"You awarded {score.points_awarded} points for {score.criterion_id} "
                "with no evidence. Quote the span of the answer that earns them, or "
                "award 0."
            )

    if not isinstance(result, TurnResult):
        return

    question = result.next_question.strip()
    if not question:
        raise ValidationViolation("The next question is empty. Write one question.")

    unknown = [c for c in result.targets_criterion_ids if c not in rubric_ids]
    if unknown:
        raise ValidationViolation(
            f"The next question targets criteria not in the rubric: {unknown}."
        )

    # Repetition guard. The state is what prevents topic level repetition;
    # this catches the narrower case of near identical wording.
    prior = state.prior_questions()
    match, score = most_similar_prior(question, prior)
    if match is not None and score >= QUESTION_SIMILARITY_THRESHOLD:
        remaining = ", ".join(state.criteria_remaining) or "none"
        raise ValidationViolation(
            f"Your question repeats one already asked. You wrote {question!r}, and "
            f"you already asked {match!r}. Ask about something different. Criteria "
            f"not yet probed: {remaining}."
        )


# ---------------------------------------------------------------------
# Stage 5: evaluation. backend.md 5.5
# ---------------------------------------------------------------------


def validate_evaluation(evaluation: Evaluation) -> None:
    if not EVAL_MIN_STRENGTHS <= len(evaluation.strengths) <= EVAL_MAX_STRENGTHS:
        raise ValidationViolation(
            f"You returned {len(evaluation.strengths)} strengths. Return between "
            f"{EVAL_MIN_STRENGTHS} and {EVAL_MAX_STRENGTHS}."
        )
    if not EVAL_MIN_CONCERNS <= len(evaluation.concerns) <= EVAL_MAX_CONCERNS:
        raise ValidationViolation(
            f"You returned {len(evaluation.concerns)} concerns. Return between "
            f"{EVAL_MIN_CONCERNS} and {EVAL_MAX_CONCERNS}."
        )
    for item in [*evaluation.strengths, *evaluation.concerns]:
        if not item.strip():
            raise ValidationViolation(
                "One of the strengths or concerns is empty. Every entry must be a "
                "complete sentence naming something specific."
            )


# ---------------------------------------------------------------------
# Stage 0: job description parsing. Feeds the Create Job form.
# ---------------------------------------------------------------------


def validate_job_facts(facts: JobFacts) -> None:
    """Check what the form needs, and nothing more.

    Deliberately lenient compared with the scoring validators. A missing
    field here is a legitimate answer, because the whole design of this
    stage is that the model returns null rather than guessing. The only
    hard requirement is a usable description body, since that is the one
    field HR cannot reconstruct from the form itself.

    The skills ceiling exists because the field feeds a TagInput. Twenty
    chips is not a better answer than eight; it means the model listed
    every noun in the document.
    """
    if len(facts.description.strip()) < JOB_FACTS_MIN_DESCRIPTION_CHARS:
        raise ValidationViolation(
            f"The description you returned is {len(facts.description.strip())} "
            f"characters, which is too short to build a rubric from. Return the "
            f"role's responsibilities and requirements in at least "
            f"{JOB_FACTS_MIN_DESCRIPTION_CHARS} characters, using the document's "
            f"own wording."
        )
    if len(facts.skills) > JOB_FACTS_MAX_SKILLS:
        raise ValidationViolation(
            f"You listed {len(facts.skills)} skills. Return at most "
            f"{JOB_FACTS_MAX_SKILLS}, keeping the concrete tools and "
            f"technologies and dropping general qualities."
        )
    for skill in facts.skills:
        if not skill.strip():
            raise ValidationViolation("One of the skills is empty. Remove it.")


# ---------------------------------------------------------------------
# Resume profile. Feeds Candidate Detail, never a score.
# ---------------------------------------------------------------------


def validate_resume_profile(profile: ResumeProfile) -> None:
    """Check only what would render badly.

    Deliberately permissive. Every field is allowed to be absent, because
    the whole design of this stage is that a sparse resume produces a
    sparse profile rather than an invented one. There is nothing to check
    the numbers against here, unlike the scoring stages, because there are
    no numbers.
    """
    if len(profile.skills) > RESUME_PROFILE_MAX_SKILLS:
        raise ValidationViolation(
            f"You listed {len(profile.skills)} skills. Return at most "
            f"{RESUME_PROFILE_MAX_SKILLS}, keeping the ones the resume names "
            f"most prominently."
        )
    for entry in profile.experience:
        if len(entry.highlights) > RESUME_PROFILE_MAX_HIGHLIGHTS:
            raise ValidationViolation(
                f"The entry for {entry.organisation} has {len(entry.highlights)} "
                f"highlights. Return at most {RESUME_PROFILE_MAX_HIGHLIGHTS} per "
                f"role, choosing the most concrete."
            )
        if not entry.organisation.strip():
            raise ValidationViolation(
                "An experience entry has no organisation. Every entry needs the "
                "employer as the resume names it."
            )
    for entry in profile.education:
        if not entry.institution.strip():
            raise ValidationViolation(
                "An education entry has no institution. Every entry needs the "
                "school or university as the resume names it."
            )
    # Observed on a real resume: a PDF hyperlink whose anchor text is
    # "Kaggle" extracts as the bare word, and the model returned that word
    # as a link. Rendering it as an anchor would produce a link to nowhere,
    # so the model is told to correct it rather than the value being
    # silently dropped here.
    for link in profile.links:
        if not _LINK_RE.match(link.strip()):
            raise ValidationViolation(
                f"{link!r} is not a URL. The links field takes full addresses "
                f"only, and the resume text often keeps just the label of a "
                f"hyperlink. Return an empty list when no real URLs appear."
            )

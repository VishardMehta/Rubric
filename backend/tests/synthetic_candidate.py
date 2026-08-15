"""Play a full interview against a scripted candidate, then grade the
interviewer.

    cd backend && .venv/bin/python -m tests.synthetic_candidate
    cd backend && .venv/bin/python -m tests.synthetic_candidate --persona vague

backend.md section 11. The only way to test an adaptive interviewer
without human subjects: a model plays a candidate with a fixed persona and
answers every question, then a second call grades the **interviewer**, not
the candidate.

Two personas, and the vague one is the important one. A strong candidate
makes any interviewer look good because there is always something concrete
to follow up on. A candidate who answers everything with "we used best
practices" is what makes a reactive interviewer loop, drift off the rubric,
or start handing over the answer it wants to hear.

Real API calls, so this runs on demand rather than in CI. Run it after any
change to the plan or turn prompts.

Adapted from the interviewer-grading approach in IliaLarchenko/Interviewer,
see docs/prior-art.md.
"""

from __future__ import annotations

import argparse
import logging
import sys

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.integrations.llm import generate_structured
from app.services.interview import (
    InterviewState,
    advance_turn,
    generate_plan,
    opening_question,
    planned_question_count,
)
from tests.fixtures.rubrics import valid_rubric

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PERSONAS = {
    "strong": (
        "You are Priya Nair, a backend engineer with five years of Python and "
        "Django experience, interviewing for a senior role. You owned a "
        "product recommendation service at Zoho serving 200,000 daily active "
        "users, and you cut its p95 latency from 400ms to 48ms by replacing "
        "request-time scoring with a pre-computed table refreshed on a "
        "schedule. You once handled a cache stampede after a deploy by adding "
        "a jittered refresh and a rebuild lock. You mentor two juniors. You "
        "have never personally handled a database failover and you say so "
        "plainly when asked rather than bluffing. Answer in first person, "
        "conversationally, 60 to 110 words, with specific numbers and named "
        "technologies. Never mention that you are an AI or that this is a "
        "simulation."
    ),
    "vague": (
        "You are a backend developer interviewing for a senior role, and you "
        "are a weak interviewee: you speak in generalities and almost never "
        "give a specific number, system name, or concrete decision. You say "
        "things like 'we followed best practices', 'it was a standard setup', "
        "'the usual tools', 'we optimised it', 'it worked well'. When pressed "
        "for detail you restate the same generality in different words rather "
        "than inventing specifics. You are not hostile and you are not silent, "
        "just persistently unspecific. Answer in first person, 40 to 80 words. "
        "Never mention that you are an AI or that this is a simulation."
    ),
}


class CandidateAnswer(BaseModel):
    answer: str = Field(description="The candidate's spoken answer, in first person.")


class InterviewerGrade(BaseModel):
    """The interviewer is what is under test, not the candidate."""

    no_repeats: bool = Field(
        description=(
            "True when no question re-asks something an earlier question "
            "already covered and the candidate already answered."
        )
    )
    coverage: bool = Field(
        description=(
            "True when every rubric criterion listed was probed by at least "
            "one question."
        )
    )
    anchoring: bool = Field(
        description=(
            "True when follow-up questions reference specifics the candidate "
            "actually said, rather than being generic questions that could "
            "have been asked before the interview started. If the candidate "
            "gave no specifics to anchor to, judge whether the interviewer "
            "pressed for specifics rather than moving on."
        )
    )
    progression: bool = Field(
        description=(
            "True when later questions go deeper into fewer topics rather "
            "than skating across more topics."
        )
    )
    no_leaking: bool = Field(
        description=(
            "True when no question hands the candidate the answer it is "
            "looking for. A question naming the expected technique is a leak."
        )
    )
    notes: str = Field(
        description=(
            "Two or three sentences on the interviewer's weakest behaviour, "
            "quoting the question number that shows it."
        )
    )


def _answer_as(persona: str, question: str, history: list[tuple[str, str]]) -> str:
    transcript = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in history)
    user = (
        f"The interview so far:\n\n{transcript or '(this is the first question)'}\n\n"
        f"The interviewer just asked:\n{question}\n\nAnswer it."
    )
    return generate_structured(PERSONAS[persona], user, CandidateAnswer).answer


def _grade(rubric, history: list[tuple[str, str]]) -> InterviewerGrade:
    transcript = "\n\n".join(
        f"Q{i}: {q}\nA{i}: {a}" for i, (q, a) in enumerate(history, start=1)
    )
    criteria = "\n".join(f"- {c.name}: {c.description}" for c in rubric.criteria)
    system = (
        "You grade technical interviewers. You are assessing the INTERVIEWER's "
        "questions, not the candidate's answers. A weak candidate does not "
        "make an interviewer bad; failing to press a weak candidate does. "
        "Judge only what the questions did."
    )
    user = (
        f"Rubric criteria the interview was supposed to cover:\n{criteria}\n\n"
        f"Transcript:\n\n{transcript}\n\nGrade the interviewer."
    )
    return generate_structured(system, user, InterviewerGrade)


def run(persona: str) -> int:
    settings = get_settings()
    if settings.demo_mode:
        sys.exit(
            "DEMO_MODE is on, so the candidate's answers would replay from "
            "cassettes and the interview would not adapt. Turn it off."
        )
    if not settings.gemini_keys():
        sys.exit("Set GEMINI_API_KEY in backend/.env.")

    rubric = valid_rubric()
    total = planned_question_count(rubric)
    plan = generate_plan(rubric, None)
    state = InterviewState.initial(rubric)

    question = opening_question()
    first = plan.slot(1)
    state.record_question(1, question, first.criterion_ids if first else [])

    print(f"Persona: {persona}. {total} questions.\n")
    history: list[tuple[str, str]] = []

    for slot in range(1, total + 1):
        answer = _answer_as(persona, question, history)
        history.append((question, answer))
        print(f"Q{slot}: {question}")
        print(f"A{slot}: {answer[:150]}{'...' if len(answer) > 150 else ''}\n")

        is_final = slot >= total
        result = advance_turn(rubric, plan, state, slot, answer, is_final)
        answered = plan.slot(slot)
        state.record_answer(
            slot, answer, 30, result, answered.criterion_ids if answered else []
        )
        if is_final:
            break
        state.record_question(slot + 1, result.next_question, result.targets_criterion_ids)
        question = result.next_question

    print("Grading the interviewer.\n")
    grade = _grade(rubric, history)

    checks = {
        "no_repeats": grade.no_repeats,
        "coverage": grade.coverage,
        "anchoring": grade.anchoring,
        "progression": grade.progression,
        "no_leaking": grade.no_leaking,
    }
    for name, passed in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print(f"\n{grade.notes}")

    # Uncovered criteria are reported from the state object rather than
    # taken on the grader's word: this is a fact we track, not a judgement.
    uncovered = state.criteria_remaining
    if uncovered:
        names = [
            (rubric.by_id(cid).name if rubric.by_id(cid) else cid) for cid in uncovered
        ]
        print(f"\nCriteria never probed, per the state object: {', '.join(names)}")

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print(f"\nFAIL: {', '.join(failed)}")
        return 1
    print("\nPASS: all five interviewer checks.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--persona",
        choices=sorted(PERSONAS),
        default="strong",
        help="vague is the one that finds real problems",
    )
    args = parser.parse_args()
    return run(args.persona)


if __name__ == "__main__":
    raise SystemExit(main())

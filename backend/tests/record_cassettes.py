"""Record the golden cassettes from one real end-to-end run.

    cd backend && .venv/bin/python -m tests.record_cassettes

This calls Gemini and Groq for real, on the free tier, exactly once per
stage. It writes three files into tests/cassettes/, which are committed:
DEMO_MODE replays from them, and a demo machine with no network and no
keys must still be able to run the whole product.

Run this after any change to a prompt. A prompt edit changes the cassette
key, so the old recording stops matching and DEMO_MODE will miss loudly
rather than replay the answer to a question no longer being asked.

What "golden" means here: one job, one strong candidate, one full
interview, evaluated. That is the path a demo walks, and nothing else is
recorded, because everything recorded has to be re-recorded on every
prompt change.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Recording must be on before anything imports the cassette module, since
# the seams read this at call time.
os.environ["RUBRIC_RECORD_CASSETTES"] = "1"

from app import cassettes
from app.core.config import get_settings
from app.integrations import storage
from app.integrations.demo_supabase import DemoClient
from app.models import Rubric
from app.services.interview import (
    InterviewState,
    advance_turn,
    evaluate_interview,
    generate_plan,
    new_token,
    opening_question,
)
from app.services.scoring import band_for
from app.services.screening import screen_candidate

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("record")

FIXTURES = Path(__file__).parent / "fixtures"

GOLDEN_JOB = {
    "title": "Senior Python Developer",
    "description": (
        "We are hiring a senior backend engineer to own our Python services. "
        "You will design and ship REST APIs with Django, model and tune "
        "PostgreSQL schemas under real load, and take production ownership of "
        "what you build, including on-call for your own services. You will "
        "work closely with product on tradeoffs and mentor two junior "
        "engineers. We care about people who can explain why they made a "
        "decision, not just what the decision was."
    ),
    "skills": ["Python", "Django", "PostgreSQL", "REST APIs", "System design"],
    "experience": "4 to 7 years",
}

GOLDEN_CANDIDATE = {
    "name": "Priya Nair",
    "email": "priya@example.com",
    "resume_text": (
        "Priya Nair. Backend engineer, five years. Zoho, 2021 to present: "
        "Python, Django, PostgreSQL. Owned a product recommendation service "
        "serving 200,000 daily active users end to end, from schema design "
        "to production monitoring. Reduced p95 latency from 400ms to 48ms by "
        "replacing request-time scoring with a pre-computed table. Mentored "
        "two junior engineers. Earlier: Freshworks, 2019 to 2021, Django and "
        "REST APIs."
    ),
    "transcript": (
        "Hi, I am Priya. I am a backend engineer with about five years of "
        "experience, mostly Python and Django with PostgreSQL underneath. "
        "Most recently at Zoho I owned a product recommendation service that "
        "served around 200,000 daily active users. I was responsible for it "
        "end to end, from the schema design through to production "
        "monitoring. The part I am most proud of is the latency work. We "
        "were scoring recommendations at request time and sitting at about "
        "400 milliseconds at p95, which was too slow. I moved us to a "
        "pre-computed table refreshed on a schedule, so the read path became "
        "a single indexed lookup and we came down to about 48 milliseconds. "
        "The tradeoff was freshness, so I talked it through with the product "
        "manager and we agreed a refresh interval we were both happy with. "
        "I also mentor two junior engineers on the team."
    ),
}

# The scripted answers the golden candidate gives, in slot order. Real
# transcription is recorded separately from real audio; these stand in for
# what that audio said, so the interview stages can be recorded without a
# microphone in the loop.
GOLDEN_ANSWERS = [
    GOLDEN_CANDIDATE["transcript"],
    (
        "I kept the read path simple. The recommendation API was a single "
        "Django REST endpoint that read from a pre-computed table rather "
        "than scoring at request time. We refreshed that table on a "
        "schedule, so the endpoint was a straight indexed lookup and stayed "
        "under 50 milliseconds even at peak. For the write side, the refresh "
        "job wrote into a staging table and we swapped it in, so readers "
        "never saw a half-built result set."
    ),
    (
        "The hardest incident was a cache stampede after a deploy. The "
        "refresh job and the deploy landed together, every worker missed "
        "cache at once and the database saturated. I added a jittered "
        "refresh and a lock around the rebuild so only one worker does the "
        "work, wrote up the postmortem, and walked the product manager "
        "through the freshness tradeoff so we could agree the refresh "
        "interval properly rather than me picking it alone."
    ),
    (
        "For schema changes I use Django migrations, and for anything on a "
        "large table I do it in two steps: add the column nullable, "
        "backfill in batches, then add the constraint. On indexing I look at "
        "the query plan first rather than guessing. The recommendation table "
        "had a composite index on user id and score, which is what made the "
        "lookup fast."
    ),
    (
        "Honestly, I have not had to handle a full primary failover myself. "
        "We ran managed Postgres, so failover was the provider's job. I know "
        "what I would look at, connection draining and making sure retries "
        "are idempotent, but I have not done it in anger and I would not "
        "want to claim otherwise."
    ),
    (
        "With the two juniors I mostly work through review. I try to ask "
        "what they expected to happen rather than telling them what is "
        "wrong, because that usually finds the mental model that is off. "
        "One of them shipped the batching for the backfill I mentioned, and "
        "I deliberately let them own it end to end rather than taking it "
        "back when it got slow."
    ),
    (
        "The thing I would change is that I did not write the postmortem "
        "until two days later, and by then I had lost some of the detail on "
        "the timeline. Now I take rough notes during the incident even when "
        "it feels like it is slowing me down."
    ),
]


def _require_keys() -> None:
    settings = get_settings()
    missing = []
    if not settings.gemini_keys():
        missing.append("GEMINI_API_KEY")
    if not settings.groq_api_key:
        missing.append("GROQ_API_KEY (optional, the local model is used instead)")
    if settings.demo_mode:
        sys.exit(
            "DEMO_MODE is on. Recording needs the live providers.\n"
            "Unset DEMO_MODE in backend/.env and run again."
        )
    if "GEMINI_API_KEY" in missing:
        sys.exit("Set GEMINI_API_KEY in backend/.env before recording.")


def main() -> int:
    _require_keys()

    # Everything is written into a fresh in-memory store, then dumped as the
    # seed. Recording never touches the real Supabase project: a recording
    # run that wrote rows would leave the demo database full of test data.
    client = DemoClient()
    storage.get_client.cache_clear()
    storage.get_client = lambda: client  # type: ignore[assignment]

    logger.info("1/5 rubric")
    from app.api.jobs import _generate_rubric

    job_row = storage.create_job(**GOLDEN_JOB)
    rubric = _generate_rubric(
        GOLDEN_JOB["title"],
        GOLDEN_JOB["description"],
        GOLDEN_JOB["skills"],
        GOLDEN_JOB["experience"],
    )
    job_row = storage.set_job_rubric(job_row["id"], rubric)
    rubric = Rubric.model_validate(job_row["rubric"])

    logger.info("2/5 transcription")
    audio = _golden_audio()
    if audio:
        from app.integrations.stt import transcribe

        spoken = transcribe(audio, "introduction.webm")
        logger.info("transcribed %d bytes: %.60s...", len(audio), spoken)
    else:
        # No audio fixture present. The interview and application flows in
        # DEMO_MODE will still work for anything typed, but a real browser
        # recording will miss. Recorded explicitly so the gap is visible in
        # the demo checklist rather than discovered live.
        logger.warning(
            "no audio fixture at %s - browser recordings will miss in DEMO_MODE",
            FIXTURES / "golden-introduction.webm",
        )

    logger.info("3/5 screening")
    candidate = storage.create_candidate(
        job_id=job_row["id"],
        name=GOLDEN_CANDIDATE["name"],
        email=GOLDEN_CANDIDATE["email"],
        resume_path=None,
        resume_text=GOLDEN_CANDIDATE["resume_text"],
        audio_path=None,
        transcript=GOLDEN_CANDIDATE["transcript"],
    )
    screening = screen_candidate(
        rubric,
        GOLDEN_CANDIDATE["transcript"],
        GOLDEN_CANDIDATE["resume_text"],
        GOLDEN_JOB["skills"],
    )
    storage.save_screening(
        candidate["id"],
        score=screening.total_score,
        band=band_for(screening.total_score),
        sub_scores=[s.model_dump() for s in screening.sub_scores],
        matched_skills=screening.matched_skills,
        unevidenced_skills=screening.unevidenced_skills,
        conflicts=screening.resume_intro_conflicts,
        assessment=screening.assessment,
        recommendation=screening.recommendation,
    )
    logger.info("screened at %d (%s)", screening.total_score, screening.recommendation)

    logger.info("4/5 interview plan and turns")
    interview = storage.create_interview(candidate["id"], new_token())
    plan = generate_plan(rubric, candidate)
    state = InterviewState.initial(rubric)

    question = opening_question()
    first = plan.slot(1)
    state.record_question(1, question, first.criterion_ids if first else [])
    interview = storage.start_interview(
        interview["id"],
        plan=plan.model_dump(),
        total_questions=len(plan.questions),
        state=state.to_dict(),
    )
    storage.create_turn(interview["id"], 1, question, first.criterion_ids if first else [])
    storage.set_candidate_state(candidate["id"], "interviewing")

    total = interview["total_questions"]
    for slot in range(1, total + 1):
        answer = GOLDEN_ANSWERS[min(slot - 1, len(GOLDEN_ANSWERS) - 1)]
        is_final = slot >= total
        result = advance_turn(rubric, plan, state, slot, answer, is_final)

        answered = plan.slot(slot)
        state.record_answer(
            slot, answer, 30, result, answered.criterion_ids if answered else []
        )
        storage.save_answer(
            interview["id"],
            slot,
            answer_text=answer,
            answer_audio_path=None,
            answer_scores=[s.model_dump() for s in result.answer_scores],
            response_time_seconds=30,
        )
        logger.info("  turn %d/%d recorded", slot, total)

        if not is_final:
            state.record_question(slot + 1, result.next_question, result.targets_criterion_ids)
            storage.update_interview_state(interview["id"], state.to_dict())
            storage.create_turn(
                interview["id"], slot + 1, result.next_question, result.targets_criterion_ids
            )

    storage.complete_interview(interview["id"], state.to_dict())
    storage.set_candidate_state(candidate["id"], "interviewed")

    logger.info("5/5 evaluation")
    accumulated = []
    for turn in storage.list_turns(interview["id"]):
        for raw in turn.get("answer_scores") or []:
            from app.models import AnswerScore

            accumulated.append(AnswerScore.model_validate(raw))
    evaluation, scores = evaluate_interview(rubric, state, accumulated)
    storage.save_interview_result(
        interview["id"],
        overall=scores["overall"],
        technical=scores["technical"],
        communication=scores["communication"],
        experience=scores["experience"],
        band=band_for(scores["overall"]),
        strengths=evaluation.strengths,
        concerns=evaluation.concerns,
        recommendation=evaluation.recommendation,
    )
    storage.mark_interview_evaluated(interview["id"])
    logger.info("evaluated at %d overall", scores["overall"])

    cassettes.supabase_record(client.snapshot())

    counts = cassettes.status()
    logger.info(
        "done. gemini=%d stt=%d supabase_rows=%d",
        counts["gemini"],
        counts["stt"],
        counts["supabase_rows"],
    )
    print("\nRecorded into", cassettes.CASSETTE_DIR)
    print("Now verify offline:  .venv/bin/python -m pytest tests/test_demo_mode.py -v")
    return 0


def _golden_audio() -> bytes | None:
    path = FIXTURES / "golden-introduction.webm"
    return path.read_bytes() if path.exists() else None


if __name__ == "__main__":
    raise SystemExit(main())

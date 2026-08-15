"""Interview routes. backend.md section 4.

Three candidate-facing routes identified only by an opaque token, and one
HR-facing result route.

The candidate never sees a score at any point, including on completion
(product.md section 2). None of these responses carry one.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.api.candidates import owned_candidate_or_404
from app.core.auth import HRUser, require_hr
from app.core.errors import (
    EvaluationFailed,
    InterviewAlreadyComplete,
    InvalidToken,
    JobNotActive,
    RubricError,
)
from app.integrations import storage
from app.integrations.stt import transcribe
from app.models import (
    AnswerScore,
    InterviewPlan,
    InterviewResult,
    InterviewSession,
    Rubric,
    TurnAdvanced,
    TurnResult,
)
from app.services.interview import (
    InterviewState,
    advance_turn,
    evaluate_interview,
    generate_plan,
    opening_question,
    planned_question_count,
)
from app.services.scoring import band_for

logger = logging.getLogger("rubric.api.interview")

router = APIRouter(tags=["interview"])

# Stage names streamed to the candidate mid-turn. These are identifiers,
# not display strings: the wording lives in the frontend next to the rest
# of the candidate-facing copy, so a change of phrasing is not a change of
# API. design-system.md section 15 defines what each one may claim.
STAGE_TRANSCRIBING = "transcribing"
STAGE_PREPARING = "preparing"
STAGE_REVIEWING = "reviewing"


def _load(token: str) -> tuple[dict, dict, dict, Rubric]:
    """Resolve a token to (interview, candidate, job, rubric).

    An unknown token is a 404 with a neutral message. It deliberately does
    not distinguish "never existed" from "belongs to someone else".
    """
    interview = storage.get_interview_by_token(token)
    if interview is None:
        raise InvalidToken()

    candidate = storage.get_candidate(interview["candidate_id"])
    if candidate is None:
        raise InvalidToken()

    job = storage.get_job(candidate["job_id"])
    if job is None or not job.get("rubric"):
        raise JobNotActive("This role is no longer available.")

    return interview, candidate, job, Rubric.model_validate(job["rubric"])


def _current_question(interview: dict) -> tuple[int, str] | None:
    """The slot and text of the question awaiting an answer, if any.

    Returning this from GET is what makes a mid-interview refresh resume
    at the right place instead of restarting (backend.md section 4).
    """
    turns = storage.list_turns(interview["id"])
    for turn in turns:
        if turn.get("answered_at") is None:
            return turn["slot"], turn["question"]
    return None


@router.get("/interview/{token}", response_model=InterviewSession)
async def get_session(token: str) -> InterviewSession:
    interview, candidate, job, rubric = _load(token)

    pending = _current_question(interview)
    return InterviewSession(
        status=interview["status"],
        job_title=job["title"],
        candidate_name=candidate["name"],
        # Before the interview starts there is no plan and so no stored
        # count, but the ready screen has to tell the candidate how many
        # questions they are agreeing to (screens.md section 7, stage 1).
        # The count is a pure function of the rubric, so this is the number
        # the plan will use, not an estimate of it.
        total_questions=interview.get("total_questions") or planned_question_count(rubric),
        current_slot=pending[0] if pending else None,
        current_question=pending[1] if pending else None,
    )


@router.post("/interview/{token}/start", response_model=InterviewSession)
async def start_interview(token: str) -> InterviewSession:
    interview, candidate, job, rubric = _load(token)

    if interview["status"] in ("complete", "evaluated"):
        raise InterviewAlreadyComplete()

    # Already started: hand back the question they were on rather than
    # regenerating the plan and losing their progress.
    if interview["status"] == "in_progress":
        return await get_session(token)

    plan = generate_plan(rubric, candidate)
    state = InterviewState.initial(rubric)

    first = plan.slot(1)
    question = opening_question()
    state.record_question(1, question, first.criterion_ids if first else [])

    interview = storage.start_interview(
        interview["id"],
        plan=plan.model_dump(),
        total_questions=len(plan.questions),
        state=state.to_dict(),
    )
    storage.create_turn(
        interview["id"], 1, question, first.criterion_ids if first else []
    )
    storage.set_candidate_state(candidate["id"], "interviewing")

    return InterviewSession(
        status="in_progress",
        job_title=job["title"],
        candidate_name=candidate["name"],
        total_questions=interview["total_questions"],
        current_slot=1,
        current_question=question,
    )


def _advance(
    token: str,
    slot: int,
    response_time_seconds: int | None,
    audio_bytes: bytes,
    filename: str | None,
    content_type: str | None,
) -> Iterator[str | TurnAdvanced]:
    """Run one interview turn, yielding a stage name before each slow step.

    This is a generator so the two routes below can share one implementation
    while presenting it differently: `/answer` drains it and returns the
    final value, `/answer/stream` forwards each stage to the browser as it
    starts.

    The stage names exist because design-system.md section 15 requires the
    candidate-facing label to name the work actually happening, and section
    22 forbids stages that advance on a timer. A turn takes 5 to 10 seconds
    and the candidate is watching the whole time, so the label has to be
    driven from here rather than guessed at in the frontend.

    Each stage is yielded *before* the work it describes, so the label is on
    screen while that work runs rather than after it finishes.
    """
    interview, candidate, _job, rubric = _load(token)

    if interview["status"] in ("complete", "evaluated"):
        raise InterviewAlreadyComplete()
    if interview["status"] != "in_progress":
        raise InvalidToken("This interview has not been started yet.")

    plan = InterviewPlan.model_validate(interview["plan"])
    state = InterviewState(interview.get("state_object"))
    total = interview["total_questions"]

    # Transcribe before writing anything, so a failed transcription leaves
    # the turn unanswered and the candidate can simply record it again.
    yield STAGE_TRANSCRIBING
    extension = (filename or "answer.webm").rsplit(".", 1)[-1].lower()
    transcript = transcribe(audio_bytes, f"answer.{extension}")

    audio_path = storage.upload(
        storage.BUCKET_ANSWERS,
        f"{interview['id']}/{slot}-{uuid.uuid4().hex[:8]}.{extension}",
        audio_bytes,
        content_type or "audio/webm",
    )

    is_final = slot >= total
    # The same model call scores this answer and writes the next question,
    # so there is one stage here and not two.
    yield STAGE_REVIEWING if is_final else STAGE_PREPARING
    result = advance_turn(rubric, plan, state, slot, transcript, is_final)

    answered = plan.slot(slot)
    probed = answered.criterion_ids if answered else []
    state.record_answer(slot, transcript, response_time_seconds, result, probed)

    storage.save_answer(
        interview["id"],
        slot,
        answer_text=transcript,
        answer_audio_path=audio_path,
        answer_scores=[s.model_dump() for s in result.answer_scores],
        response_time_seconds=response_time_seconds,
    )

    if not is_final and isinstance(result, TurnResult):
        next_slot = slot + 1
        state.record_question(
            next_slot, result.next_question, result.targets_criterion_ids
        )
        storage.update_interview_state(interview["id"], state.to_dict())
        storage.create_turn(
            interview["id"],
            next_slot,
            result.next_question,
            result.targets_criterion_ids,
        )
        yield TurnAdvanced(
            status="in_progress",
            next_slot=next_slot,
            next_question=result.next_question,
            total_questions=total,
        )
        return

    # Final answer: close the interview, then evaluate.
    storage.complete_interview(interview["id"], state.to_dict())
    storage.set_candidate_state(candidate["id"], "interviewed")

    try:
        _evaluate(interview["id"], rubric, state)
    except Exception:
        # The interview itself is complete and every answer is saved. A
        # failed evaluation is an HR-side problem to retry, not something
        # to surface to a candidate who has finished and done nothing
        # wrong.
        logger.exception("evaluation failed for interview %s", interview["id"])

    yield TurnAdvanced(status="complete", total_questions=total)


@router.post("/interview/{token}/answer", response_model=TurnAdvanced)
async def submit_answer(
    token: str,
    slot: int = Form(...),
    response_time_seconds: int | None = Form(None),
    audio: UploadFile = File(...),
) -> TurnAdvanced:
    """The plain route. Stage names are discarded; the result is returned as
    one JSON object with a real status code. Used by curl and by tests."""
    audio_bytes = await audio.read()
    final: TurnAdvanced | None = None
    for item in _advance(
        token, slot, response_time_seconds, audio_bytes, audio.filename, audio.content_type
    ):
        if isinstance(item, TurnAdvanced):
            final = item
    assert final is not None  # the generator always yields a result last
    return final


@router.post("/interview/{token}/answer/stream")
async def submit_answer_streaming(
    token: str,
    slot: int = Form(...),
    response_time_seconds: int | None = Form(None),
    audio: UploadFile = File(...),
) -> StreamingResponse:
    """The same turn, as newline-delimited JSON, so the candidate's screen
    can name the step that is running right now.

    Errors are delivered in the body rather than as a status code: the
    response has already begun by the time anything slow can fail, so the
    status is committed. The envelope matches errors.py exactly, and the
    frontend raises the same ApiError from it either way.
    """
    audio_bytes = await audio.read()
    filename, content_type = audio.filename, audio.content_type

    def emit() -> Iterator[str]:
        try:
            for item in _advance(
                token, slot, response_time_seconds, audio_bytes, filename, content_type
            ):
                if isinstance(item, TurnAdvanced):
                    yield json.dumps({"result": item.model_dump()}) + "\n"
                else:
                    yield json.dumps({"stage": item}) + "\n"
        except RubricError as exc:
            logger.error("streamed turn failed code=%s: %s", exc.code, exc)
            yield json.dumps(
                {
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "retryable": exc.retryable,
                    }
                }
            ) + "\n"
        except Exception:
            logger.exception("streamed turn failed unexpectedly")
            yield json.dumps(
                {
                    "error": {
                        "code": "internal_error",
                        "message": "Something went wrong. Try again.",
                        "retryable": True,
                    }
                }
            ) + "\n"

    return StreamingResponse(
        emit(),
        media_type="application/x-ndjson",
        # Without this a proxy or the browser can hold the first lines back
        # and deliver every stage at once when the request finishes, which
        # would defeat the entire point of streaming them.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _evaluate(interview_id: str, rubric: Rubric, state: InterviewState) -> None:
    accumulated: list[AnswerScore] = []
    for turn in storage.list_turns(interview_id):
        for raw in turn.get("answer_scores") or []:
            accumulated.append(AnswerScore.model_validate(raw))

    evaluation, scores = evaluate_interview(rubric, state, accumulated)

    storage.save_interview_result(
        interview_id,
        overall=scores["overall"],
        technical=scores["technical"],
        communication=scores["communication"],
        experience=scores["experience"],
        band=band_for(scores["overall"]),
        strengths=evaluation.strengths,
        concerns=evaluation.concerns,
        recommendation=evaluation.recommendation,
    )
    storage.mark_interview_evaluated(interview_id)


@router.get("/candidates/{candidate_id}/interview", response_model=InterviewResult)
async def get_result(
    candidate_id: str, hr: HRUser = Depends(require_hr)
) -> InterviewResult:
    """HR-facing. The full result with every turn.

    Owner scoped like the rest of the candidate routes. This one returns
    the entire transcript plus signed URLs to every answer recording, so
    leaving it open would undo the scoping on all the others.
    """
    candidate, job = owned_candidate_or_404(candidate_id, hr)

    interview = storage.get_interview_by_candidate(candidate_id)
    if interview is None:
        raise InvalidToken("This candidate has no interview.")

    rubric = Rubric.model_validate(job["rubric"]) if job and job.get("rubric") else None
    result = storage.get_interview_result(interview["id"])
    turns = storage.list_turns(interview["id"])

    def criterion_names(ids: list[str]) -> list[str]:
        if not rubric:
            return ids
        return [(rubric.by_id(i).name if rubric.by_id(i) else i) for i in ids]

    return InterviewResult(
        candidate_id=candidate_id,
        candidate_name=candidate["name"],
        job_title=job["title"] if job else "",
        status=interview["status"],
        total_questions=interview.get("total_questions"),
        completed_at=interview.get("completed_at"),
        overall_score=result["overall_score"] if result else None,
        technical_score=result["technical_score"] if result else None,
        communication_score=result["communication_score"] if result else None,
        experience_score=result["experience_score"] if result else None,
        band=result["band"] if result else None,
        strengths=result["strengths"] if result else [],
        concerns=result["concerns"] if result else [],
        recommendation=result["recommendation"] if result else None,
        turns=[
            {
                "slot": t["slot"],
                "question": t["question"],
                "answer_text": t.get("answer_text"),
                "criteria": criterion_names(t.get("criterion_ids") or []),
                "response_time_seconds": t.get("response_time_seconds"),
                "audio_url": storage.signed_url(
                    storage.BUCKET_ANSWERS, t.get("answer_audio_path")
                ),
            }
            for t in turns
        ],
    )


@router.post("/candidates/{candidate_id}/interview/evaluate", response_model=InterviewResult)
async def retry_evaluation(
    candidate_id: str, hr: HRUser = Depends(require_hr)
) -> InterviewResult:
    """Retry an evaluation that failed after the candidate finished."""
    _candidate, job = owned_candidate_or_404(candidate_id, hr)

    interview = storage.get_interview_by_candidate(candidate_id)
    if interview is None:
        raise InvalidToken("That candidate has no interview.")

    if not job.get("rubric"):
        raise JobNotActive("That job no longer has a rubric to score against.")

    state = InterviewState(interview.get("state_object"))
    try:
        _evaluate(interview["id"], Rubric.model_validate(job["rubric"]), state)
    except Exception:
        logger.exception("evaluation retry failed for interview %s", interview["id"])
        raise EvaluationFailed() from None

    return await get_result(candidate_id, hr)

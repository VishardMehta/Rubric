"""The candidate application route. backend.md section 4.

Everything runs synchronously inside the request: upload, extract,
transcribe, screen, save. It takes 8 to 20 seconds and the browser shows
real progress labels for the duration (screens.md section 6). No queue, no
workers, no polling endpoint - see backend.md section 1.

Order matters. The candidate row is inserted before screening runs, so a
screening failure leaves their audio, transcript and resume intact and HR
can retry from the dashboard instead of asking them to apply again.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.core.errors import JobNotActive, RubricError, ScreeningFailed
from app.integrations import storage
from app.integrations.resume import extract_resume
from app.integrations.stt import transcribe
from app.models import CandidateCreated, Rubric
from app.services.scoring import band_for
from app.services.screening import screen_candidate

logger = logging.getLogger("rubric.api.apply")

router = APIRouter(tags=["apply"])

# Stage names streamed to the candidate during submission. Identifiers, not
# display strings - the wording lives in the frontend (design-system.md
# section 15 names these exactly: "Transcribing introduction" then "Scoring
# against rubric"; "Uploading" is shown client-side before the first line
# arrives, the same way the interview screen shows it before its own first
# stage).
STAGE_READING_RESUME = "reading_resume"
STAGE_TRANSCRIBING = "transcribing"
STAGE_SCORING = "scoring"

# Chrome records webm/opus, Safari records mp4. Both are sent straight to
# the transcription provider, which infers the container from the
# extension, so the original extension is preserved on upload.
_AUDIO_EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


def _audio_extension(content_type: str | None, filename: str | None) -> str:
    if content_type:
        base = content_type.split(";")[0].strip().lower()
        if base in _AUDIO_EXTENSIONS:
            return _AUDIO_EXTENSIONS[base]
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "webm"


def _apply(
    job_id: str,
    name: str,
    email: str,
    resume_bytes: bytes,
    audio_bytes: bytes,
    audio_filename: str | None,
    audio_content_type: str | None,
) -> Iterator[str | CandidateCreated]:
    """Run one application, yielding a stage name before each slow step.

    Shared by the plain route, which drains it, and the streaming route,
    which forwards each stage to the browser as it starts. See
    `interview._advance` for the identical pattern and the reasoning:
    design-system.md section 15 requires the label to name the work
    actually happening, and this takes 8 to 20 seconds with the candidate
    watching the whole time.
    """
    job = storage.get_job(job_id)
    if job is None:
        raise JobNotActive("That job could not be found.")
    if job["state"] != "active" or not job.get("rubric"):
        raise JobNotActive()

    rubric = Rubric.model_validate(job["rubric"])

    # Read and parse both files before touching the database, so a bad
    # upload fails fast without leaving a half written candidate row.
    yield STAGE_READING_RESUME
    resume_text = extract_resume(resume_bytes)

    yield STAGE_TRANSCRIBING
    extension = _audio_extension(audio_content_type, audio_filename)
    transcript = transcribe(audio_bytes, f"introduction.{extension}")

    candidate_uuid = str(uuid.uuid4())
    resume_path = storage.upload(
        storage.BUCKET_RESUMES,
        f"{job_id}/{candidate_uuid}.pdf",
        resume_bytes,
        "application/pdf",
    )
    audio_path = storage.upload(
        storage.BUCKET_INTRODUCTIONS,
        f"{job_id}/{candidate_uuid}.{extension}",
        audio_bytes,
        audio_content_type or "audio/webm",
    )

    # Raises AlreadyApplied if this email already applied for this job.
    candidate = storage.create_candidate(
        job_id=job_id,
        name=name.strip(),
        email=email.strip().lower(),
        resume_path=resume_path,
        resume_text=resume_text,
        audio_path=audio_path,
        transcript=transcript,
    )

    yield STAGE_SCORING
    try:
        result = screen_candidate(
            rubric, transcript, resume_text, job.get("skills") or []
        )
    except Exception:
        logger.exception("screening failed for candidate %s", candidate["id"])
        storage.mark_screening_failed(candidate["id"])
        raise ScreeningFailed() from None

    storage.save_screening(
        candidate["id"],
        score=result.total_score,
        band=band_for(result.total_score),
        sub_scores=[s.model_dump() for s in result.sub_scores],
        matched_skills=result.matched_skills,
        unevidenced_skills=result.unevidenced_skills,
        conflicts=result.resume_intro_conflicts,
        assessment=result.assessment,
        recommendation=result.recommendation,
    )

    # The candidate is told their application was received and nothing
    # more. They never see a score, a band or a recommendation
    # (product.md section 2).
    yield CandidateCreated(id=candidate["id"], job_title=job["title"])


@router.post("/apply/{job_id}", response_model=CandidateCreated)
async def submit_application(
    job_id: str,
    name: str = Form(...),
    email: str = Form(...),
    resume: UploadFile = File(...),
    audio: UploadFile = File(...),
) -> CandidateCreated:
    """The plain route. Stage names are discarded. Used by curl and tests."""
    resume_bytes = await resume.read()
    audio_bytes = await audio.read()
    final: CandidateCreated | None = None
    for item in _apply(
        job_id, name, email, resume_bytes, audio_bytes, audio.filename, audio.content_type
    ):
        if isinstance(item, CandidateCreated):
            final = item
    assert final is not None  # the generator always yields a result last
    return final


@router.post("/apply/{job_id}/stream")
async def submit_application_streaming(
    job_id: str,
    name: str = Form(...),
    email: str = Form(...),
    resume: UploadFile = File(...),
    audio: UploadFile = File(...),
) -> StreamingResponse:
    """The same application, as newline-delimited JSON. See
    `interview.submit_answer_streaming` for the identical envelope and the
    reasoning: the response has already begun by the time anything slow can
    fail, so errors arrive as a body line rather than a status code."""
    resume_bytes = await resume.read()
    audio_bytes = await audio.read()
    audio_filename, audio_content_type = audio.filename, audio.content_type

    def emit() -> Iterator[str]:
        try:
            for item in _apply(
                job_id, name, email, resume_bytes, audio_bytes, audio_filename, audio_content_type
            ):
                if isinstance(item, CandidateCreated):
                    yield json.dumps({"result": item.model_dump()}) + "\n"
                else:
                    yield json.dumps({"stage": item}) + "\n"
        except RubricError as exc:
            logger.error("streamed application failed code=%s: %s", exc.code, exc)
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
            logger.exception("streamed application failed unexpectedly")
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

"""The one error shape used everywhere. backend.md section 9.

`message` is user-facing prose and goes straight into the UI. It never
contains a stack trace, a provider name, a status code or a model id - if
you're tempted to put one of those in a message, log it instead and write a
plain sentence for the message.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("rubric")


class RubricError(Exception):
    """Base for every error the API can raise on purpose."""

    code: str = "internal_error"
    status_code: int = 500
    retryable: bool = False
    default_message: str = "Something went wrong. Try again."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class RubricGenerationFailed(RubricError):
    code = "rubric_generation_failed"
    status_code = 502
    retryable = True
    default_message = (
        "The model provider did not respond in time. Your job description is saved."
    )


class ScreeningFailed(RubricError):
    code = "screening_failed"
    status_code = 502
    retryable = True
    default_message = (
        "Screening could not be completed. The candidate's introduction and "
        "transcript are saved."
    )


class TranscriptionFailed(RubricError):
    code = "transcription_failed"
    status_code = 502
    retryable = True
    default_message = "We could not hear that clearly. Try recording it again."


class EvaluationFailed(RubricError):
    code = "evaluation_failed"
    status_code = 502
    retryable = True
    default_message = "The interview could not be evaluated. Your answers are saved."


class SchemaValidationFailed(RubricError):
    code = "schema_validation_failed"
    status_code = 502
    retryable = True
    default_message = "The model provider returned an unexpected response. Try again."


class AudioTooLarge(RubricError):
    code = "audio_too_large"
    status_code = 413
    retryable = False
    default_message = "That recording is too large. Try a shorter answer."


class ResumeTooLarge(RubricError):
    code = "resume_too_large"
    status_code = 413
    retryable = False
    default_message = "That file is over 5 MB. Try exporting it again at a smaller size."


class ResumeNotReadable(RubricError):
    code = "resume_not_readable"
    status_code = 400
    retryable = False
    default_message = (
        "This resume appears to be a scanned image. Upload a PDF with selectable text."
    )


class ResumeWrongFormat(RubricError):
    code = "resume_wrong_format"
    status_code = 400
    retryable = False
    default_message = "Rubric reads PDF resumes. Export yours as a PDF and try again."


class AudioUnreadable(RubricError):
    code = "audio_unreadable"
    status_code = 400
    retryable = False
    default_message = "We could not read that audio file. Try recording again."


class InvalidToken(RubricError):
    code = "invalid_token"
    status_code = 404
    retryable = False
    default_message = "This link is no longer valid."


class InterviewAlreadyComplete(RubricError):
    code = "interview_already_complete"
    status_code = 409
    retryable = False
    default_message = "This interview has already been completed."


class JobNotActive(RubricError):
    code = "job_not_active"
    status_code = 409
    retryable = False
    default_message = "This job is no longer accepting applications."


class AlreadyApplied(RubricError):
    """The (job_id, email) unique constraint fired. Re-application is out
    of scope (product.md section 7), so this is a clear message rather
    than a 500 from a raw database error."""

    code = "already_applied"
    status_code = 409
    retryable = False
    default_message = (
        "You have already applied for this role. Only one application per "
        "person is accepted."
    )


class CandidateNotFound(RubricError):
    code = "candidate_not_found"
    status_code = 404
    retryable = False
    default_message = "That candidate could not be found."


class RateLimited(RubricError):
    code = "rate_limited"
    status_code = 429
    retryable = True
    default_message = "Rubric is receiving a lot of requests. Try again shortly."


def install_error_handlers(app: FastAPI) -> None:
    """Register the RubricError -> JSON response mapping on the app."""

    @app.exception_handler(RubricError)
    async def handle_rubric_error(request: Request, exc: RubricError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.error(
            "request_id=%s code=%s path=%s: %s",
            request_id,
            exc.code,
            request.url.path,
            repr(exc),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.exception("request_id=%s unhandled error at %s", request_id, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Try again.",
                    "retryable": True,
                }
            },
        )

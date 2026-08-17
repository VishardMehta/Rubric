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

from app.core.config import get_settings

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


class JobDescriptionTooLarge(RubricError):
    code = "job_description_too_large"
    status_code = 413
    retryable = False
    default_message = "That job description is over 10 MB. Export a smaller PDF and try again."


class JobDescriptionUnreadable(RubricError):
    code = "job_description_unreadable"
    status_code = 400
    retryable = False
    default_message = "Rubric could not read text from that PDF. Upload a PDF with selectable text."


class JobDescriptionWrongFormat(RubricError):
    code = "job_description_wrong_format"
    status_code = 400
    retryable = False
    default_message = "Upload the job description as a PDF."


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


class SchemaOutOfDate(RubricError):
    """A write the code supports and the database does not, because a
    migration in database/ has not been run against this project.

    Named rather than left as a 500. The failure is real and the fix is one
    file, so the message says which file instead of making someone read a
    constraint name out of a stack trace mid-demo."""

    code = "schema_out_of_date"
    status_code = 500
    retryable = False
    default_message = "This database is missing a migration from database/."


class CandidateAlreadyDecided(RubricError):
    """Hiring someone who has been rejected, or rejecting someone who has
    been hired. Both are terminal, and there is no route back out of either:
    reversing a decision means reopening the application, which is out of
    scope. A clear 409 beats writing a state that contradicts the one
    already recorded."""

    code = "candidate_already_decided"
    status_code = 409
    retryable = False
    default_message = "A final decision has already been recorded for this candidate."


class CandidateNotFound(RubricError):
    code = "candidate_not_found"
    status_code = 404
    retryable = False
    default_message = "That candidate could not be found."


class DatabaseUnavailable(RubricError):
    """The database did not answer, after retries.

    Distinct from the backend being down, and the distinction is the whole
    point of this class. A bare 500 here reached the frontend, which mapped
    it to "Rubric could not reach the server" - so a running backend with a
    briefly unreachable database read as a dead backend, and the person
    debugging went looking at uvicorn instead of at Supabase.

    503 rather than 500: the request was well formed and the service is
    temporarily unable to serve it. Retryable, because it usually is.
    """

    code = "database_unavailable"
    status_code = 503
    retryable = True
    default_message = (
        "Rubric could not reach its database. This is usually a paused "
        "Supabase project or a brief network drop. Try again in a moment."
    )


class RateLimited(RubricError):
    code = "rate_limited"
    status_code = 429
    retryable = True
    default_message = "Rubric is receiving a lot of requests. Try again shortly."


class ProviderTimeout(RubricError):
    """The model provider accepted the request and did not answer in time.

    Distinct from SchemaValidationFailed, which means the provider answered
    with something unusable. Conflating them sends the user a message about
    an unexpected response when nothing was received at all, and hides a
    real capacity problem behind a wording that suggests a bug.
    """

    code = "provider_timeout"
    status_code = 504
    retryable = True
    default_message = (
        "The model provider did not respond in time. Nothing was lost. Try again."
    )


class NotAuthenticated(RubricError):
    """No session token, or one that has expired or been signed out.

    The frontend keys its "send them to the sign in screen" behavior off
    this code, so it must stay distinct from InvalidCredentials, which
    means the credentials were wrong on a login attempt that was never
    going to carry a session in the first place.
    """

    code = "not_authenticated"
    status_code = 401
    retryable = False
    default_message = "Sign in to continue."


class InvalidCredentials(RubricError):
    """Wrong email or wrong password.

    One message for both. Saying which half was wrong tells an attacker
    which addresses have accounts.
    """

    code = "invalid_credentials"
    status_code = 401
    retryable = False
    default_message = "That email and password do not match an account."


class EmailAlreadyRegistered(RubricError):
    code = "email_already_registered"
    status_code = 409
    retryable = False
    default_message = "An account already exists for that email. Sign in instead."


class WeakPassword(RubricError):
    code = "weak_password"
    status_code = 400
    retryable = False
    default_message = "Use a longer password."


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
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Try again.",
                    "retryable": True,
                }
            },
        )
        _allow_origin(request, response)
        return response


def _allow_origin(request: Request, response: JSONResponse) -> None:
    """Put the CORS header back on a 500.

    This handler runs inside Starlette's ServerErrorMiddleware, which sits
    *outside* CORSMiddleware, so its response never passes through the
    middleware that would add Access-Control-Allow-Origin. The browser then
    blocks a response the backend did send, fetch() throws, and the
    frontend reports "Rubric could not reach the server" for a backend that
    is running and answering.

    That is how a database blip read as a dead process, and it cost real
    debugging time looking at uvicorn instead of at Supabase.

    The origin is echoed only when it is already on the configured
    allowlist, so this does not widen CORS - it stops a 500 from silently
    narrowing it.
    """
    origin = request.headers.get("origin")
    if origin and origin in get_settings().cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin

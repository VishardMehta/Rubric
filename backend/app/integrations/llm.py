"""Gemini client and the shared structured-call-with-retry helper.

Every LLM stage (backend.md section 5) goes through generate_structured:
one call, parsed straight into a Pydantic model via response_schema, no
free-text parsing anywhere. If the caller's validator finds a problem - a
rubric that doesn't sum to 100, evidence that isn't a real quote - it raises
ValidationViolation with a plain-English description of what was wrong, and
that description is appended to a single retry. A second failure is never
silently repaired; it becomes a retryable error the caller (or the HR user)
can act on.

Temperature is pinned at 0 with a fixed seed. The same transcript scored
twice must not drift - see CLAUDE.md "Scoring discipline". That is the
property the consistency harness in Phase 3 measures.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.errors import RateLimited, SchemaValidationFailed
from app.core.heuristics import (
    LLM_REQUEST_TIMEOUT_SECONDS,
    LLM_SEED,
    LLM_TEMPERATURE,
    LLM_TRANSIENT_BACKOFF_SECONDS,
    LLM_TRANSIENT_RETRIES,
)

logger = logging.getLogger("rubric.llm")

T = TypeVar("T", bound=BaseModel)


class ValidationViolation(Exception):
    """Raised by a stage's validator when structured output fails a
    post-generation check.

    The message is written as retry guidance for the model, not as user
    facing prose. It is sent back to Gemini verbatim and logged, but it is
    never returned in an API response - see errors.py, where `message` is
    documented as text that goes straight into the UI.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@lru_cache
def _get_client(key_index: int) -> genai.Client:
    """One cached client per configured key. Keys are addressed by index so
    the cache stays keyed on something that is not itself a secret."""
    settings = get_settings()
    keys = settings.gemini_keys()
    if not keys:
        raise SchemaValidationFailed(
            "The model provider is not configured. Set GEMINI_API_KEY in backend/.env."
        )
    return genai.Client(
        api_key=keys[min(key_index, len(keys) - 1)],
        # HttpOptions.timeout is in milliseconds.
        http_options=genai_types.HttpOptions(timeout=LLM_REQUEST_TIMEOUT_SECONDS * 1000),
    )


def _call(
    system_instruction: str,
    user_content: str,
    response_model: type[T],
    key_index: int = 0,
) -> T:
    settings = get_settings()
    client = _get_client(key_index)

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_content,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_model,
            temperature=LLM_TEMPERATURE,
            seed=LLM_SEED,
            # Nothing here uses tools. Disabling this keeps the SDK from
            # logging an automatic-function-calling advisory on every call.
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )

    if response.parsed is not None:
        return response.parsed  # type: ignore[return-value]

    # The SDK could not auto-parse (rare, but possible on a truncated or
    # malformed response). Validate the raw text ourselves so a near miss
    # surfaces as our error type rather than a raw pydantic traceback.
    if not response.text:
        logger.error("gemini returned no parseable content")
        raise SchemaValidationFailed()
    try:
        return response_model.model_validate_json(response.text)
    except ValidationError as exc:
        logger.error("could not validate gemini response against %s: %s", response_model.__name__, exc)
        raise SchemaValidationFailed() from exc


def _call_with_key_failover(
    system_instruction: str,
    user_content: str,
    response_model: type[T],
    key_count: int,
) -> T:
    """Try each configured key in turn on a rate limit.

    Free-tier quota is per key, so a second key is a second quota. A 429
    during a client demo is unrecoverable in the moment (CLAUDE.md), and
    this is the cheapest mitigation available. Only 429 rotates: any other
    error means the request itself is the problem, and retrying it against
    a different key would just burn the second quota too.
    """
    for key_index in range(key_count):
        try:
            return _call_with_transient_retry(
                system_instruction, user_content, response_model, key_index
            )
        except genai_errors.ClientError as exc:
            if exc.code != 429:
                raise
            is_last = key_index == key_count - 1
            if is_last:
                logger.error("all %d gemini key(s) rate limited", key_count)
                raise RateLimited() from exc
            logger.warning(
                "gemini key %d rate limited, trying key %d", key_index + 1, key_index + 2
            )
    raise RateLimited()


def _call_with_transient_retry(
    system_instruction: str,
    user_content: str,
    response_model: type[T],
    key_index: int,
) -> T:
    """Retry briefly on a provider side outage.

    A 5xx means the request was fine and the provider was not. Treating it
    as terminal throws away real work: observed live, a 503 on the last
    interview turn discarded a completed interview. Rate limits are not
    retried here - those rotate to the other key instead.
    """
    for attempt in range(LLM_TRANSIENT_RETRIES + 1):
        try:
            return _call(system_instruction, user_content, response_model, key_index)
        except genai_errors.ServerError as exc:
            if attempt == LLM_TRANSIENT_RETRIES:
                logger.error(
                    "gemini unavailable after %d attempts: %s",
                    LLM_TRANSIENT_RETRIES + 1,
                    exc,
                )
                raise
            wait = LLM_TRANSIENT_BACKOFF_SECONDS * (attempt + 1)
            logger.warning(
                "gemini server error (%s), retrying in %.1fs", exc.code, wait
            )
            time.sleep(wait)
    raise SchemaValidationFailed()


def generate_structured(
    system_instruction: str,
    user_content: str,
    response_model: type[T],
    *,
    validate: Callable[[T], None] | None = None,
    max_retries: int = 1,
) -> T:
    """Call Gemini, validate, retry at most once with the violation stated.

    Never retries past max_retries and never repairs output in Python: the
    caller gets a real error instead of a number nobody checked. A rubric
    silently adjusted to sum to 100 no longer matches what the model
    reasoned about (backend.md 5.1).
    """
    last_violation: ValidationViolation | None = None
    attempt_content = user_content
    key_count = max(len(get_settings().gemini_keys()), 1)

    for attempt in range(max_retries + 1):
        try:
            result = _call_with_key_failover(
                system_instruction, attempt_content, response_model, key_count
            )
        except genai_errors.ClientError as exc:
            logger.error("gemini client error code=%s: %s", exc.code, exc)
            raise SchemaValidationFailed() from exc
        except genai_errors.ServerError as exc:
            logger.warning("gemini server error code=%s: %s", exc.code, exc)
            raise SchemaValidationFailed() from exc

        if validate is None:
            return result

        try:
            validate(result)
            return result
        except ValidationViolation as violation:
            last_violation = violation
            logger.warning(
                "validation violation on attempt %d/%d: %s",
                attempt + 1,
                max_retries + 1,
                violation.message,
            )
            attempt_content = (
                f"{user_content}\n\n"
                f"Your previous response was invalid: {violation.message}\n"
                "Correct this and return a complete, valid response."
            )

    # Exhausted retries. Log the developer-facing violation; return the
    # generic user-facing prose from errors.py rather than leaking it.
    logger.error(
        "giving up after %d attempts, last violation: %s",
        max_retries + 1,
        last_violation.message if last_violation else "unknown",
    )
    raise SchemaValidationFailed()

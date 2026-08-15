"""The shared structured-call helper. Gemini is mocked throughout - these
test the retry contract, not the provider.

The contract that matters: validate, retry at most once with the violation
stated in the prompt, then fail. Never repair output in Python, and never
leak the developer-facing violation text into a user-facing message.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from app.core.errors import RateLimited, SchemaValidationFailed
from app.integrations import llm
from app.integrations.llm import ValidationViolation, generate_structured


class Reply(BaseModel):
    value: int


def _sequence_of(*values: int):
    """A fake _call returning the given values in order, recording the
    prompt it was handed each time."""
    calls: list[str] = []
    iterator = iter(values)

    def _call(system: str, user: str, model: type[BaseModel], key_index: int = 0):
        calls.append(user)
        return Reply(value=next(iterator))

    return _call, calls


def test_returns_first_result_when_no_validator(monkeypatch):
    call, _ = _sequence_of(1)
    monkeypatch.setattr(llm, "_call", call)
    assert generate_structured("sys", "user", Reply).value == 1


def test_returns_first_result_when_validation_passes(monkeypatch):
    call, calls = _sequence_of(1)
    monkeypatch.setattr(llm, "_call", call)

    result = generate_structured("sys", "user", Reply, validate=lambda r: None)

    assert result.value == 1
    assert len(calls) == 1


def test_retries_once_and_states_the_violation(monkeypatch):
    call, calls = _sequence_of(1, 2)
    monkeypatch.setattr(llm, "_call", call)

    def validate(reply: Reply) -> None:
        if reply.value != 2:
            raise ValidationViolation("value must be 2, you sent 1")

    result = generate_structured("sys", "the original prompt", Reply, validate=validate)

    assert result.value == 2
    assert len(calls) == 2
    # The retry keeps the original prompt and appends the violation, so the
    # model has both the task and what it got wrong.
    assert calls[0] == "the original prompt"
    assert "the original prompt" in calls[1]
    assert "value must be 2, you sent 1" in calls[1]


def test_gives_up_after_max_retries_without_repairing(monkeypatch):
    call, calls = _sequence_of(1, 1)
    monkeypatch.setattr(llm, "_call", call)

    def validate(reply: Reply) -> None:
        raise ValidationViolation("always wrong")

    with pytest.raises(SchemaValidationFailed):
        generate_structured("sys", "user", Reply, validate=validate)

    assert len(calls) == 2  # initial attempt plus one retry, then stop


def test_failure_message_does_not_leak_violation_text(monkeypatch):
    """errors.py documents `message` as prose shown directly in the UI.
    A validator's arithmetic complaint must not end up in front of an HR
    user."""
    call, _ = _sequence_of(1, 1)
    monkeypatch.setattr(llm, "_call", call)

    def validate(reply: Reply) -> None:
        raise ValidationViolation("sub-scores sum to 71 but total_score is 72")

    with pytest.raises(SchemaValidationFailed) as exc:
        generate_structured("sys", "user", Reply, validate=validate)

    assert "sub-scores" not in exc.value.message
    assert "71" not in exc.value.message


def test_respects_higher_max_retries(monkeypatch):
    call, calls = _sequence_of(1, 1, 3)
    monkeypatch.setattr(llm, "_call", call)

    def validate(reply: Reply) -> None:
        if reply.value != 3:
            raise ValidationViolation("not yet")

    result = generate_structured("sys", "user", Reply, validate=validate, max_retries=2)

    assert result.value == 3
    assert len(calls) == 3


def test_rate_limit_maps_to_rate_limited(monkeypatch):
    from google.genai import errors as genai_errors

    def _call(system, user, model, key_index=0):
        raise genai_errors.ClientError(429, {"error": {"message": "quota"}}, None)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key", "k1")
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key_2", "")

    with pytest.raises(RateLimited):
        generate_structured("sys", "user", Reply)


def test_other_client_errors_map_to_schema_validation_failed(monkeypatch):
    from google.genai import errors as genai_errors

    def _call(system, user, model, key_index=0):
        raise genai_errors.ClientError(400, {"error": {"message": "bad request"}}, None)

    monkeypatch.setattr(llm, "_call", _call)

    with pytest.raises(SchemaValidationFailed):
        generate_structured("sys", "user", Reply)


def test_server_error_maps_to_schema_validation_failed(monkeypatch):
    from google.genai import errors as genai_errors

    def _call(system, user, model, key_index=0):
        raise genai_errors.ServerError(503, {"error": {"message": "overloaded"}}, None)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm, "LLM_TRANSIENT_BACKOFF_SECONDS", 0)

    with pytest.raises(SchemaValidationFailed):
        generate_structured("sys", "user", Reply)


def test_unparseable_response_raises_rather_than_returning_none(monkeypatch):
    """If the SDK cannot parse and there is no text to fall back on, that
    must surface as our error type, not as a None the caller then uses."""
    response = MagicMock()
    response.parsed = None
    response.text = ""

    client = MagicMock()
    client.models.generate_content.return_value = response
    monkeypatch.setattr(llm, "_get_client", lambda idx=0: client)

    with pytest.raises(SchemaValidationFailed):
        llm._call("sys", "user", Reply)


def test_malformed_json_fallback_raises_our_error(monkeypatch):
    response = MagicMock()
    response.parsed = None
    response.text = "{not valid json"

    client = MagicMock()
    client.models.generate_content.return_value = response
    monkeypatch.setattr(llm, "_get_client", lambda idx=0: client)

    with pytest.raises(SchemaValidationFailed):
        llm._call("sys", "user", Reply)


def test_second_key_used_when_first_is_rate_limited(monkeypatch):
    """Free-tier quota is per key, so a second key is a second quota.
    A 429 mid-demo is unrecoverable, and this is the cheap mitigation."""
    from google.genai import errors as genai_errors

    seen_indexes: list[int] = []

    def _call(system, user, model, key_index=0):
        seen_indexes.append(key_index)
        if key_index == 0:
            raise genai_errors.ClientError(429, {"error": {"message": "quota"}}, None)
        return Reply(value=7)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key", "key-one")
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key_2", "key-two")

    result = generate_structured("sys", "user", Reply)

    assert result.value == 7
    assert seen_indexes == [0, 1]


def test_all_keys_rate_limited_raises_rate_limited(monkeypatch):
    from google.genai import errors as genai_errors

    attempts: list[int] = []

    def _call(system, user, model, key_index=0):
        attempts.append(key_index)
        raise genai_errors.ClientError(429, {"error": {"message": "quota"}}, None)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key", "key-one")
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key_2", "key-two")

    with pytest.raises(RateLimited):
        generate_structured("sys", "user", Reply)

    assert attempts == [0, 1]


def test_non_rate_limit_error_does_not_burn_the_second_key(monkeypatch):
    """A 400 means the request is wrong. Retrying it on another key would
    just spend the backup quota on the same bad request."""
    from google.genai import errors as genai_errors

    attempts: list[int] = []

    def _call(system, user, model, key_index=0):
        attempts.append(key_index)
        raise genai_errors.ClientError(400, {"error": {"message": "bad"}}, None)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key", "key-one")
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key_2", "key-two")

    with pytest.raises(SchemaValidationFailed):
        generate_structured("sys", "user", Reply)

    assert attempts == [0]


def test_temperature_and_seed_are_pinned(monkeypatch):
    """Score stability is this product's load-bearing property. Running
    scoring at Gemini's default temperature would make the Phase 3
    consistency harness fail for a reason that looks like a weak prompt."""
    from app.core.heuristics import LLM_SEED, LLM_TEMPERATURE

    response = MagicMock()
    response.parsed = Reply(value=1)

    client = MagicMock()
    client.models.generate_content.return_value = response
    monkeypatch.setattr(llm, "_get_client", lambda idx=0: client)

    llm._call("sys", "user", Reply)

    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.temperature == LLM_TEMPERATURE == 0.0
    assert config.seed == LLM_SEED
    assert config.response_mime_type == "application/json"
    assert config.response_schema is Reply


def test_transient_server_error_is_retried(monkeypatch):
    """A 5xx means the request was fine and the provider was not. Observed
    live: a 503 on the final interview turn would otherwise discard a
    completed interview."""
    from google.genai import errors as genai_errors

    attempts = []

    def _call(system, user, model, key_index=0):
        attempts.append(1)
        if len(attempts) < 3:
            raise genai_errors.ServerError(503, {"error": {"message": "high demand"}}, None)
        return Reply(value=9)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm, "LLM_TRANSIENT_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key", "k1")
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key_2", "")

    assert generate_structured("sys", "user", Reply).value == 9
    assert len(attempts) == 3


def test_transient_retry_eventually_gives_up(monkeypatch):
    from google.genai import errors as genai_errors

    attempts = []

    def _call(system, user, model, key_index=0):
        attempts.append(1)
        raise genai_errors.ServerError(503, {"error": {"message": "high demand"}}, None)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm, "LLM_TRANSIENT_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key", "k1")
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key_2", "")

    with pytest.raises(SchemaValidationFailed):
        generate_structured("sys", "user", Reply)
    assert len(attempts) == llm.LLM_TRANSIENT_RETRIES + 1


def test_rate_limit_is_not_transient_retried(monkeypatch):
    """429 rotates to the other key rather than waiting on the same one."""
    from google.genai import errors as genai_errors

    per_key = {}

    def _call(system, user, model, key_index=0):
        per_key[key_index] = per_key.get(key_index, 0) + 1
        raise genai_errors.ClientError(429, {"error": {"message": "quota"}}, None)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm, "LLM_TRANSIENT_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key", "k1")
    monkeypatch.setattr(llm.get_settings(), "gemini_api_key_2", "k2")

    with pytest.raises(RateLimited):
        generate_structured("sys", "user", Reply)
    # Each key tried exactly once, not retried with backoff.
    assert per_key == {0: 1, 1: 1}


def test_read_timeout_is_retried_then_reported_as_a_timeout(monkeypatch):
    """A slow provider must not look like a schema failure.

    Observed live during the consistency harness: the fourth of five
    identical calls timed out and propagated as a bare 500. A timeout is
    the same category as a 5xx - the request was fine, the provider did
    not answer - so it retries, and if it keeps timing out the caller gets
    a timeout, not "unexpected response".
    """
    import httpx

    from app.core.errors import ProviderTimeout
    from app.integrations import llm
    from app.models import Rubric

    calls = {"n": 0}

    def always_times_out(*args, **kwargs):
        calls["n"] += 1
        raise httpx.ReadTimeout("the read operation timed out")

    monkeypatch.setattr(llm, "_call", always_times_out)
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)

    with pytest.raises(ProviderTimeout) as caught:
        llm.generate_structured("sys", "usr", Rubric)

    assert calls["n"] == llm.LLM_TRANSIENT_RETRIES + 1
    assert "did not respond in time" in str(caught.value)


def test_a_timeout_that_clears_on_retry_succeeds(monkeypatch):
    """The point of retrying: one slow call must not discard real work."""
    import httpx

    from app.integrations import llm
    from app.models import Rubric
    from tests.fixtures.rubrics import valid_rubric

    rubric = valid_rubric()
    calls = {"n": 0}

    def slow_once(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("the read operation timed out")
        return rubric

    monkeypatch.setattr(llm, "_call", slow_once)
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)

    result = llm.generate_structured("sys", "usr", Rubric)

    assert calls["n"] == 2
    assert sum(c.points for c in result.criteria) == 100

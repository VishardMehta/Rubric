"""backend.md section 11: test_stt_falls_back_on_429.

Groq's client is mocked throughout - no real API key or recorded audio is
needed to prove the *routing* logic (which errors fall back, which surface
immediately). Live verification against real Chrome/Safari clips and a real
GROQ_API_KEY happens once, manually, before the first demo - see
docs/implementation-plan.md 10.7.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import groq
import pytest

from app.core.errors import AudioTooLarge, AudioUnreadable, TranscriptionFailed
from app.core.heuristics import AUDIO_MAX_BYTES
from app.integrations import stt

FAKE_AUDIO = b"\x1aE\xdf\xa3" + b"0" * 1024  # webm-ish magic bytes, content irrelevant


@pytest.fixture(autouse=True)
def _configure_groq_key(monkeypatch):
    monkeypatch.setattr(stt.get_settings(), "groq_api_key", "test-key")


def _mock_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


def test_groq_success_short_circuits_local(monkeypatch):
    monkeypatch.setattr(stt, "_transcribe_with_groq", lambda audio, filename: "hello world")
    local_called = MagicMock()
    monkeypatch.setattr(stt, "_transcribe_locally", local_called)

    result = stt.transcribe(FAKE_AUDIO, "answer.webm")

    assert result == "hello world"
    local_called.assert_not_called()


@pytest.mark.parametrize(
    "raised",
    [
        groq.RateLimitError("rate limited", response=MagicMock(status_code=429), body=None),
        groq.InternalServerError("boom", response=MagicMock(status_code=500), body=None),
        groq.APITimeoutError(request=MagicMock()),
        groq.APIConnectionError(request=MagicMock()),
    ],
)
def test_retryable_groq_errors_fall_back_to_local(monkeypatch, raised):
    def _fail(audio, filename):
        raise raised

    monkeypatch.setattr(stt, "_transcribe_with_groq", _fail)
    monkeypatch.setattr(stt, "_transcribe_locally", lambda audio, filename: "local transcript")

    result = stt.transcribe(FAKE_AUDIO, "answer.mp4")

    assert result == "local transcript"


def test_bad_request_does_not_fall_back(monkeypatch):
    def _fail(audio, filename):
        raise groq.BadRequestError(
            "bad file", response=MagicMock(status_code=400), body=None
        )

    monkeypatch.setattr(stt, "_transcribe_with_groq", _fail)
    local_called = MagicMock()
    monkeypatch.setattr(stt, "_transcribe_locally", local_called)

    with pytest.raises(AudioUnreadable):
        stt.transcribe(FAKE_AUDIO, "answer.webm")

    local_called.assert_not_called()


def test_local_failure_surfaces_as_transcription_failed(monkeypatch):
    monkeypatch.setattr(stt, "_transcribe_with_groq", lambda audio, filename: (_ for _ in ()).throw(
        groq.APIConnectionError(request=MagicMock())
    ))

    def _fail_local(audio, filename):
        raise RuntimeError("ffmpeg not found")

    monkeypatch.setattr(stt, "_transcribe_locally", _fail_local)

    with pytest.raises(TranscriptionFailed):
        stt.transcribe(FAKE_AUDIO, "answer.webm")


def test_oversized_audio_rejected_before_any_network_call(monkeypatch):
    called = MagicMock()
    monkeypatch.setattr(stt, "_transcribe_with_groq", called)

    oversized = b"0" * (AUDIO_MAX_BYTES + 1)
    with pytest.raises(AudioTooLarge):
        stt.transcribe(oversized, "answer.webm")

    called.assert_not_called()


def test_empty_audio_rejected(monkeypatch):
    with pytest.raises(AudioUnreadable):
        stt.transcribe(b"", "answer.webm")


def test_no_groq_key_goes_straight_to_local(monkeypatch):
    monkeypatch.setattr(stt.get_settings(), "groq_api_key", "")
    called_groq = MagicMock()
    monkeypatch.setattr(stt, "_transcribe_with_groq", called_groq)
    monkeypatch.setattr(stt, "_transcribe_locally", lambda audio, filename: "local only")

    result = stt.transcribe(FAKE_AUDIO, "answer.webm")

    assert result == "local only"
    called_groq.assert_not_called()

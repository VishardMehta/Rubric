"""Speech to text: Groq primary, faster-whisper local fallback.

backend.md section 7.2. Groq's whisper-large-v3-turbo is typically under 2
seconds for a 2 minute clip. The local model is the safety net for a rate
limit, a server error, a slow response, or no network at all - it is not the
everyday path, so it is not tuned for speed, just for always being there.
"""

from __future__ import annotations

import io
import logging

import groq
from faster_whisper import WhisperModel

from app import cassettes
from app.core.config import get_settings
from app.core.errors import AudioTooLarge, AudioUnreadable, TranscriptionFailed
from app.core.heuristics import AUDIO_MAX_BYTES, STT_TIMEOUT_SECONDS

logger = logging.getLogger("rubric.stt")

_local_model: WhisperModel | None = None


def _get_local_model() -> WhisperModel:
    """Loaded once at process start, not per request - backend.md 7.2."""
    global _local_model
    if _local_model is None:
        settings = get_settings()
        logger.info("loading local whisper model=%s", settings.local_whisper_model)
        _local_model = WhisperModel(
            settings.local_whisper_model,
            device="cpu",
            compute_type=settings.local_whisper_compute_type,
        )
    return _local_model


def _transcribe_with_groq(audio: bytes, filename: str) -> str:
    settings = get_settings()
    client = groq.Groq(api_key=settings.groq_api_key, timeout=STT_TIMEOUT_SECONDS)
    response = client.audio.transcriptions.create(
        file=(filename, audio),
        model=settings.groq_stt_model,
    )
    return response.text.strip()


def _transcribe_locally(audio: bytes, filename: str) -> str:
    model = _get_local_model()
    # faster-whisper reads from a file path or a file-like object; a BytesIO
    # with .name set lets it infer the container via ffmpeg the same way the
    # Groq path infers it from the filename extension.
    buffer = io.BytesIO(audio)
    buffer.name = filename
    segments, _info = model.transcribe(buffer, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()


def transcribe(audio: bytes, filename: str) -> str:
    """Groq primary, faster-whisper fallback, in that order.

    Falls back on 429, 5xx, timeout, or any connection error. Never falls
    back on a 4xx that indicates a bad file - that is a real error and
    should surface as one, not get retried against a different model.
    """
    if len(audio) > AUDIO_MAX_BYTES:
        raise AudioTooLarge()
    if len(audio) == 0:
        raise AudioUnreadable("The recording was empty. Try recording again.")

    # Size and emptiness are checked before the cassette lookup so those
    # two errors behave identically in DEMO_MODE. They are properties of
    # the file, not of the provider, and a demo should still reject a
    # 30MB upload the way the live system does.
    if cassettes.demo_mode():
        return cassettes.stt_replay(audio)

    settings = get_settings()

    if settings.groq_api_key:
        try:
            transcript = _transcribe_with_groq(audio, filename)
            if cassettes.recording():
                cassettes.stt_record(audio, transcript)
            return transcript
        except groq.BadRequestError as exc:
            raise AudioUnreadable() from exc
        except groq.AuthenticationError as exc:
            # Not a fallback trigger: a bad key is a config error, not
            # something the local model can paper over silently.
            logger.error("groq authentication failed: %s", exc)
            raise TranscriptionFailed(
                "Transcription is not configured correctly. Contact the site operator."
            ) from exc
        except (
            groq.RateLimitError,
            groq.InternalServerError,
            groq.APITimeoutError,
            groq.APIConnectionError,
        ) as exc:
            logger.warning("groq transcription failed, falling back locally: %r", exc)
    else:
        logger.info("no GROQ_API_KEY configured, using local transcription")

    try:
        transcript = _transcribe_locally(audio, filename)
        if cassettes.recording():
            cassettes.stt_record(audio, transcript)
        return transcript
    except Exception as exc:
        logger.exception("local transcription failed")
        raise TranscriptionFailed() from exc

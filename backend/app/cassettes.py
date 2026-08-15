"""Recorded provider responses, replayed when DEMO_MODE=1.

CLAUDE.md: "Free tiers rate-limit. A 429 during a client demo is
unrecoverable in the moment. Record real Gemini and Groq responses for one
golden candidate, and have DEMO_MODE=1 replay from those cassettes instead
of calling out. Build this before the first client demo, not after the
first failure."

Three things are recorded:

  gemini.json    keyed on the response schema plus a hash of the exact
                 prompt pair, so a prompt edit misses rather than silently
                 replaying the answer to a different question
  stt.json       keyed on a hash of the audio bytes
  supabase.json  the golden job, candidate, interview and turn rows, used
                 to seed the in-memory store in demo_supabase.py

**A miss raises.** It never falls through to a network call. That is the
entire point: DEMO_MODE has to be provably offline, and a store that
quietly reaches for the network when it does not recognise something would
still 429 during the demo it exists to protect. The error names the
cassette that was missing so it can be re-recorded.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import RubricError

logger = logging.getLogger("rubric.cassettes")

CASSETTE_DIR = Path(__file__).resolve().parent.parent / "tests" / "cassettes"

GEMINI_FILE = "gemini.json"
STT_FILE = "stt.json"
SUPABASE_FILE = "supabase.json"

# Set by the recorder. When on, a miss performs the real call and stores
# the result instead of raising.
RECORD_ENV = "RUBRIC_RECORD_CASSETTES"


class CassetteMiss(RubricError):
    """DEMO_MODE was on and nothing was recorded for this input."""

    code = "cassette_miss"
    status_code = 503
    retryable = False
    default_message = (
        "This demo recording is incomplete. Re-record the cassettes, or turn "
        "DEMO_MODE off to call the live providers."
    )


def demo_mode() -> bool:
    return get_settings().demo_mode


def recording() -> bool:
    return os.environ.get(RECORD_ENV) == "1"


# --- File access -----------------------------------------------------------


def _path(name: str) -> Path:
    return CASSETTE_DIR / name


def _load(name: str) -> dict[str, Any]:
    path = _path(name)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CassetteMiss(
            f"The cassette file {name} is not valid JSON. Re-record it."
        ) from exc


def _save(name: str, payload: dict[str, Any]) -> None:
    CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    _path(name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


# --- Keys ------------------------------------------------------------------


def gemini_key(system: str, user: str, schema_name: str) -> str:
    """Stage plus input hash.

    The schema name is the stage: Rubric, Screening, TurnResult and so on.
    It is included in the key so an edit to one stage's prompt cannot match
    a recording made for another, and it is kept in the clear so a human
    can read the cassette file and see which stage each entry belongs to.
    """
    digest = hashlib.sha256(
        b"\x00".join([system.encode(), user.encode(), schema_name.encode()])
    ).hexdigest()[:16]
    return f"{schema_name}:{digest}"


def audio_key(audio: bytes) -> str:
    return f"audio:{hashlib.sha256(audio).hexdigest()[:16]}"


# --- Gemini ----------------------------------------------------------------


def gemini_replay(system: str, user: str, schema_name: str) -> dict[str, Any]:
    """The recorded JSON for this call, or raise."""
    key = gemini_key(system, user, schema_name)
    store = _load(GEMINI_FILE)
    entry = store.get(key)
    if entry is None:
        logger.error("cassette miss: %s", key)
        raise CassetteMiss(
            f"No recorded {schema_name} response for this input. "
            f"Run `python -m tests.record_cassettes` with DEMO_MODE off."
        )
    return entry["response"]


def gemini_record(system: str, user: str, schema_name: str, response: dict[str, Any]) -> None:
    store = _load(GEMINI_FILE)
    store[gemini_key(system, user, schema_name)] = {
        "stage": schema_name,
        # A prompt excerpt so the file is reviewable by eye. Never the whole
        # prompt: these files are committed, and the prompts are long.
        "prompt_excerpt": user[:180],
        "response": response,
    }
    _save(GEMINI_FILE, store)
    logger.info("recorded gemini cassette for %s", schema_name)


# --- Transcription ---------------------------------------------------------


def stt_replay(audio: bytes) -> str:
    key = audio_key(audio)
    store = _load(STT_FILE)
    entry = store.get(key)
    if entry is None:
        logger.error("cassette miss: %s", key)
        raise CassetteMiss(
            "No recorded transcript for this audio. In DEMO_MODE only the "
            "golden recordings can be transcribed."
        )
    return entry["transcript"]


def stt_record(audio: bytes, transcript: str) -> None:
    store = _load(STT_FILE)
    store[audio_key(audio)] = {"bytes": len(audio), "transcript": transcript}
    _save(STT_FILE, store)
    logger.info("recorded stt cassette (%d bytes)", len(audio))


# --- Supabase seed ---------------------------------------------------------


def supabase_seed() -> dict[str, list[dict[str, Any]]]:
    """Golden rows for the in-memory store. An empty seed is allowed: it
    just means the demo starts from an empty dashboard."""
    seed = _load(SUPABASE_FILE)
    return {table: rows for table, rows in seed.items() if isinstance(rows, list)}


def supabase_record(snapshot: dict[str, list[dict[str, Any]]]) -> None:
    _save(SUPABASE_FILE, snapshot)
    logger.info(
        "recorded supabase seed: %s",
        ", ".join(f"{t}={len(r)}" for t, r in snapshot.items()) or "empty",
    )


def status() -> dict[str, int]:
    """Counts per cassette, for the recorder and the demo checklist."""
    seed = supabase_seed()
    return {
        "gemini": len(_load(GEMINI_FILE)),
        "stt": len(_load(STT_FILE)),
        "supabase_rows": sum(len(rows) for rows in seed.values()),
    }

"""Environment settings and pinned model ids.

Every value that depends on the deployment environment or on which external
model is in use lives here. Numeric thresholds that shape product behavior
(band boundaries, similarity cutoffs, size limits) live in heuristics.py
instead - this file is about *which service*, heuristics.py is about *what
counts as a pass*.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Two free-tier keys. The second is used automatically when the first is
    # rate limited, which roughly doubles usable free-tier quota. A 429
    # during a client demo is unrecoverable in the moment (CLAUDE.md), so
    # the cheapest mitigation available is worth taking.
    gemini_api_key: str = ""
    gemini_api_key_2: str = ""

    groq_api_key: str = ""

    demo_mode: bool = False

    # Pinned here, not inline at call sites, per backend.md section 2.
    #
    # gemini-3.1-flash-lite chosen for free-tier RPM/RPD headroom rather
    # than raw quality: quota is the binding constraint during development
    # and demos. Measured 2026-08-14 on a real rubric generation, all three
    # candidates returned a valid 100 point rubric:
    #   gemini-3.1-flash-lite   8.4s
    #   gemini-3.5-flash-lite   2.4s   (faster, tighter free-tier limits)
    #   gemini-3.7-flash       94.6s   (would exceed the timeout below)
    # If an interview turn feels slow in a live demo, 3.5-flash-lite is a
    # drop-in swap.
    gemini_model: str = "gemini-3.1-flash-lite"

    # console.groq.com model catalogue.
    groq_stt_model: str = "whisper-large-v3-turbo"

    # faster-whisper local fallback.
    local_whisper_model: str = "base"
    local_whisper_compute_type: str = "int8"

    # The Vite dev server, pinned to 5273 in frontend/vite.config.ts. Both
    # hostnames are listed because `localhost` and `127.0.0.1` are distinct
    # origins to the browser, and typing either into the address bar is a
    # reasonable thing to do on a localhost-only build.
    cors_origins: list[str] = [
        "http://localhost:5273",
        "http://127.0.0.1:5273",
    ]


    def gemini_keys(self) -> list[str]:
        """Configured Gemini keys in preference order, blanks removed."""
        return [k.strip() for k in (self.gemini_api_key, self.gemini_api_key_2) if k.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

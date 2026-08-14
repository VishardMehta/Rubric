"""Every threshold that shapes product behavior, named and in one place.

No numeric literal with meaning appears anywhere else in the codebase. If a
piece of code needs a magic number, it belongs here first.

Each constant cites the spec section that defines it so a future change has
somewhere to start.
"""

from __future__ import annotations

# --- Score bands -----------------------------------------------------------
# design-system.md section 3. Computed server-side; the frontend never
# derives a band from a number.

BAND_STRONG_MIN = 70
BAND_BORDERLINE_MIN = 45
# Anything below BAND_BORDERLINE_MIN is "weak".

# --- Rubric generation -------------------------------------------------
# backend.md 5.1

RUBRIC_MIN_CRITERIA = 4
RUBRIC_MAX_CRITERIA = 7
RUBRIC_TOTAL_POINTS = 100
RUBRIC_GENERATION_MAX_RETRIES = 1

# --- Interview plan ----------------------------------------------------
# backend.md 5.3, product.md section 6

PLAN_MIN_QUESTIONS = 5
PLAN_MAX_QUESTIONS = 10
PLAN_FIXED_OPENING_SLOTS = 3  # background, projects, personal contribution
PLAN_MIN_SLOT_FOR_DEEP_DEPTH = 4  # no "deep" question before this slot

# --- Interview state -----------------------------------------------------
# backend.md section 6

STATE_CLAIMS_MADE_CAP = 12  # most recent first

# --- Turn generation -----------------------------------------------------
# backend.md 5.4

# Normalised token-overlap ratio (0 to 1) above which a newly generated
# question is considered a repeat of a prior question and is regenerated.
QUESTION_SIMILARITY_THRESHOLD = 0.6
TURN_GENERATION_MAX_RETRIES = 1

# --- Evaluation ------------------------------------------------------------
# backend.md 5.5

EVAL_TECHNICAL_WEIGHT = 0.5
EVAL_COMMUNICATION_WEIGHT = 0.25
EVAL_EXPERIENCE_WEIGHT = 0.25
EVAL_OVERALL_SCORE_TOLERANCE = 2  # points, from the weighted average
EVAL_MIN_STRENGTHS = 2
EVAL_MAX_STRENGTHS = 4
EVAL_MIN_CONCERNS = 1
EVAL_MAX_CONCERNS = 4

# --- Audio ingestion -----------------------------------------------------
# backend.md 7.2

AUDIO_MAX_BYTES = 20 * 1024 * 1024  # 20MB

# Groq -> faster-whisper fallback trigger. Any single request taking longer
# than this is treated as a timeout and routed to the local model.
STT_TIMEOUT_SECONDS = 15

# --- Resume ingestion ------------------------------------------------------
# backend.md 7.1

RESUME_MAX_BYTES = 5 * 1024 * 1024  # 5MB
RESUME_MAX_CHARS = 20_000
RESUME_MIN_READABLE_CHARS = 200  # below this, treat as an image-only PDF

# --- LLM calls -------------------------------------------------------------

# Measured 2026-08-14: rubric generation ~8s, screening 5 to 16s against
# gemini-3.1-flash-lite. A 30s ceiling produced an intermittent ReadTimeout
# on screening, so there is headroom here rather than a tight fit.
LLM_REQUEST_TIMEOUT_SECONDS = 60

# Determinism knobs. These live here rather than in config.py because they
# are tuned together with CONSISTENCY_HARNESS_MAX_SCORE_RANGE below: they
# exist to hold scores steady across reruns, which is the property that
# harness measures.
#
# Temperature 0 does not make Gemini fully deterministic on its own, which
# is exactly why the sub-score discipline in CLAUDE.md matters. It removes
# the easiest source of drift; anchored per-criterion sub-scores remove the
# rest. A fixed seed is best-effort on the provider side.
LLM_TEMPERATURE = 0.0
LLM_SEED = 42

# Transient provider failures (5xx, "high demand") are separate from
# validation retries: nothing is wrong with the request, the provider is
# briefly unavailable. Observed live on 2026-08-14, a 503 on the final
# interview turn would otherwise discard an interview the candidate had
# just spent ten minutes on.
#
# Backoff is deliberately short. The candidate is sitting in front of a
# "preparing the next question" state, so a long wait reads as a hang.
LLM_TRANSIENT_RETRIES = 2
LLM_TRANSIENT_BACKOFF_SECONDS = 1.5

# --- Consistency harness ---------------------------------------------------
# backend.md section 11. There is no ground truth for screening scores, so
# variance across repeated runs on identical input is the only measurable
# property.

CONSISTENCY_HARNESS_RUNS = 5
CONSISTENCY_HARNESS_MAX_SCORE_RANGE = 8  # points, max - min across the runs

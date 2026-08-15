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

# --- HR accounts -----------------------------------------------------------
# database/002_accounts.sql. Password hashing uses hashlib.scrypt from the
# standard library, because CLAUDE.md forbids adding a dependency and
# bcrypt/argon2 would be one.

# scrypt cost parameters. n must be a power of two. These are the values
# RFC 7914 gives as interactive-login defaults, and they cost roughly 100ms
# and 16MB per hash on a laptop: slow enough to make offline cracking
# expensive, fast enough that a demo login does not feel stuck.
#
# n is stored per user in the hash record rather than assumed, so raising
# it later does not invalidate existing passwords.
PASSWORD_SCRYPT_N = 2**14
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1
PASSWORD_SCRYPT_DKLEN = 32
PASSWORD_SALT_BYTES = 16

# scrypt allocates about 128 * n * r * p bytes. Python's default cap is
# lower than that, so the limit is raised explicitly at the call site
# rather than silently failing on a memory error.
PASSWORD_SCRYPT_MAXMEM = 128 * PASSWORD_SCRYPT_N * PASSWORD_SCRYPT_R * PASSWORD_SCRYPT_P * 2

# Short enough that a forgotten open tab is not a standing risk, long
# enough that HR is not signed out mid-review.
SESSION_TTL_HOURS = 12

# Below this a password is rejected at registration. Deliberately a length
# floor and nothing else: composition rules push people toward "Passw0rd!"
# and are worse than length.
PASSWORD_MIN_LENGTH = 10

# --- Job description parsing -----------------------------------------------
# Feeds the Create Job form from an uploaded PDF.

# Below this the extracted body is not enough to build a rubric from, which
# is the same floor the Create Job form applies to a typed description.
JOB_FACTS_MIN_DESCRIPTION_CHARS = 120

# The skills field feeds a TagInput. More than this is not a better answer,
# it means the model listed every noun in the document.
JOB_FACTS_MAX_SKILLS = 12

# --- Resume profile --------------------------------------------------------
# Structured resume facts for Candidate Detail. Never feeds a score.

# Orientation, not a skills matrix. Past this the list stops being scannable
# and starts being the resume again.
RESUME_PROFILE_MAX_SKILLS = 20

# Per role. Three concrete things is a summary; ten is the original bullets.
RESUME_PROFILE_MAX_HIGHLIGHTS = 3

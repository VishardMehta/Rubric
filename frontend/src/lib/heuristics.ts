/*
 * Every frontend threshold, named and in one place.
 *
 * The mirror of backend/app/core/heuristics.py, and it exists for the same
 * reason: no numeric literal with meaning should appear anywhere else. If
 * a component needs a magic number, it belongs here first.
 *
 * Nothing here duplicates a backend threshold. Score bands, criteria
 * counts and question counts are all decided server-side and arrive in the
 * response - the frontend never recomputes one (design-system.md 3).
 */

// --- Audio capture ---------------------------------------------------------
// screens.md section 6, "Recorder states".

/** RMS below this counts as silence. Set just above the noise floor of a
 *  laptop microphone in a quiet room, so a muted or dead mic reads as
 *  silent while breathing and room tone do not. */
export const SILENCE_RMS_THRESHOLD = 0.012;

/** No input at all for this long means something is wrong with the
 *  microphone, and the caption says so in `caution`. */
export const NO_INPUT_WARNING_MS = 3000;

/** A pause this long *after speech has already been heard* is just a
 *  pause. The interview says `Still listening` rather than warning, because
 *  the candidate is thinking, not broken (screens.md section 7). */
export const STILL_LISTENING_MS = 5000;

/** Warned about, never blocked (screens.md section 6, "Validation"). */
export const SHORT_RECORDING_SECONDS = 20;

/** Safety ceiling on a single take. The backend rejects over 20MB, and
 *  webm/opus runs about 0.5MB per minute, so this stops well short. */
export const MAX_RECORDING_SECONDS = 10 * 60;

// --- Create Job ------------------------------------------------------------

/** Below this, the description is too thin to build meaningful criteria
 *  from (screens.md section 2, "Validation"). A blocking rule, not a hint:
 *  a two-line description produces a rubric that scores nobody usefully. */
export const DESCRIPTION_MIN_CHARS = 120;

// --- Resume upload -----------------------------------------------------
// screens.md section 6, "Resume upload states". Mirrors
// backend/app/core/heuristics.py RESUME_MAX_BYTES exactly, so an oversized file
// is rejected at the dropzone instead of after a round trip to the server.

export const RESUME_MAX_BYTES = 5 * 1024 * 1024;

// --- Level meter -----------------------------------------------------------

/** Bars drawn across the meter. Each is one sample of recent history, so
 *  this doubles as how far back the meter remembers. */
export const METER_BAR_COUNT = 48;

/** FFT size for the AnalyserNode. 1024 gives enough time-domain resolution
 *  for an RMS reading without costing a full frame to process. */
export const ANALYSER_FFT_SIZE = 1024;

/** How often the silence logic samples the analyser. The meter itself
 *  redraws every animation frame; this is only for the captions, which
 *  change on a human timescale and do not need 60Hz. */
export const LEVEL_SAMPLE_INTERVAL_MS = 100;

/** Raw RMS is tiny for speech. This scales it into the 0 to 1 the meter
 *  draws with, chosen so a normal speaking voice reaches roughly
 *  three-quarters height and leaves headroom before clipping. */
export const METER_GAIN = 6;

// --- Interview -------------------------------------------------------------

/** Recording begins this long after a question appears, or after speech
 *  synthesis finishes. Not a delay for its own sake: it gives the question
 *  transition time to land so the candidate is not talking over a moving
 *  screen (screens.md section 7, stage 4). */
export const AUTO_RECORD_DELAY_MS = 400;

/** A connection failure mid-interview retries this many times before the
 *  screen offers a manual reload. Answers are persisted per turn, so a
 *  reload resumes rather than restarts. */
export const TURN_RETRY_ATTEMPTS = 2;
export const TURN_RETRY_BACKOFF_MS = 1500;

/** Question transition: 320ms with an 8px rise (design-system.md 18).
 *  Kept here because the interview screen sequences it in JS as well as
 *  animating it in CSS, and the two must agree. */
export const QUESTION_TRANSITION_MS = 320;

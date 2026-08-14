# Rubric implementation plan

Sequential build plan. Work top to bottom.

Every task names its files and its done-when condition. Specifications are not
repeated here; each task points at the section that defines it.

**Ordering principle: retire risk before building surface.** The AI stages and
the audio pipeline are the only parts of this project that can fail in ways
that are hard to recover from. They are built first, verified by curl, and only
then wrapped in a UI. The first visual demo lands around day 9, and the first
working end-to-end flow, driven from a terminal, lands around day 6.

Total 15 to 17 days.

---

## Phase 0 · Foundations · 1 day

- [ ] **0.1** Supabase project created and un-paused. Three private storage
      buckets: `introductions`, `answers`, `resumes`
- [ ] **0.2** `database/schema.sql` written from `backend.md` §3 and run in the
      SQL editor. All five tables and both indexes exist
- [ ] **0.3** Backend scaffold: `pyproject.toml`, venv, `app/main.py` with CORS
      for `localhost:5273`, `app/core/config.py` reading env, `app/api/health.py`
- [ ] **0.4** `.env.example` with the four variable names and empty values.
      `.env` gitignored and filled
- [ ] **0.5** `app/core/heuristics.py` created with every threshold from the specs:
      band boundaries, criteria count bounds, claim cap, question similarity
      threshold, audio size limit, timeouts
- [ ] **0.6** Frontend scaffold: Vite React, Inter self-hosted at 400/500/600,
      `index.css` containing the full token layer from `DESIGN.md`

**Done when** `GET /api/health` returns 200 and `npm run dev` serves a blank
page with tokens loaded.

---

## Phase 1 · Ingestion · 1.5 days

Built first because it is the only component with a hard external dependency
that cannot be worked around late.

- [ ] **1.1** `app/integrations/stt.py`, Groq path, `whisper-large-v3-turbo`. Correct
      filename extension passed through so the container is inferred
- [ ] **1.2** `faster-whisper` fallback, `base`, `int8`, CPU. Model loaded once
      at process start, not per request
- [ ] **1.3** Fallback triggers per `backend.md` §7: 429, 5xx, timeout, connection
      error. Never on a 4xx indicating a bad file
- [ ] **1.4** Size guard, 20MB, returning `audio_too_large`
- [ ] **1.5** `test_stt_falls_back_on_429`. Fixture clips recorded from Chrome
      (webm/opus) and Safari (mp4) both transcribe
- [ ] **1.6** `app/integrations/resume.py`: `pypdf` extraction, whitespace normalisation,
      20,000 character cap, 5MB limit
- [ ] **1.7** Image-only detection. Under 200 extracted characters returns
      `resume_not_readable`. No OCR fallback
- [ ] **1.8** `test_image_pdf_rejected` with a scanned fixture PDF

**Done when** both browser formats transcribe through Groq, and pulling the
network mid-test routes to `faster-whisper` and still returns text.

---

## Phase 2 · Rubric generation · 1 day

- [ ] **2.1** `app/integrations/llm.py`: Gemini client, one structured-call helper taking a
      Pydantic model, retry-once-with-violation logic, timeout from
      `app/core/heuristics.py`
- [ ] **2.2** `app/models.py`: `Criterion`, `Rubric` per `backend.md` §5.1
- [ ] **2.3** `app/services/prompts.py`: `rubric_prompts()` returning `(system, user)`
- [ ] **2.4** `app/services/validation.py`: points sum to exactly 100, 4 to 7 criteria,
      unique slug ids. No silent repair
- [ ] **2.5** `app/integrations/storage.py`: Supabase client on `service_role`, job insert
      and fetch, signed-URL helper
- [ ] **2.6** `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{id}`
- [ ] **2.7** `test_rubric_points_sum`

**Done when** a curl with a real job description returns a rubric whose points
total 100, and a deliberately broken prompt fails validation rather than
returning a repaired rubric.

---

## Phase 3 · Screening · 3 days

- [ ] **3.1** `Evidence`, `SubScore`, `Screening` models per `backend.md` §5.2.
      Evidence is a list of source-tagged verbatim quotes
- [ ] **3.2** `screening_prompts()` builder
- [ ] **3.3** Validation: every criterion once, points in range, sub-scores sum
      to total, and every quote appears in the source it names. A quote
      attributed to the resume that exists only in the transcript fails
- [ ] **3.3b** `resume_intro_conflicts` populated and surfaced. No score
      penalty applied for a conflict
- [ ] **3.4** `app/services/scoring.py`: band computation from `app/core/heuristics.py`
      boundaries. Band is computed server-side and returned, never derived in
      the frontend
- [ ] **3.5** `POST /api/apply/{job_id}` multipart with `resume` and `audio`.
      Upload both, extract, transcribe, screen against both sources, insert.
      Object paths stored, never URLs
- [ ] **3.6** `GET /api/apply/{job_id}` public job summary. Title only, never
      the rubric
- [ ] **3.7** `GET /api/jobs/{id}/candidates` ranked, score descending
- [ ] **3.8** `test_subscores_sum`, `test_criteria_ids_exist`,
      `test_band_boundaries`, `test_evidence_source_matches`
- [ ] **3.9** **Consistency harness.** One fixture transcript, five runs, assert
      range under the `app/core/heuristics.py` threshold

**Done when** 3.9 passes. If it does not, the sub-score discipline is not
working and nothing downstream is trustworthy. Fix it here, not later.

---

## Phase 4 · Interview engine · 2 days

- [ ] **4.1** `PlannedQuestion`, `InterviewPlan` models per `backend.md` §5.3
- [ ] **4.2** `app/services/interview.py`: plan generation. Slots 1 to 3 fixed intents,
      every criterion covered, no `deep` before slot 4, count scaled from
      rubric breadth
- [ ] **4.3** State object per `product.md` §6, with `claims_made` capped at 12
- [ ] **4.4** `AnswerScore`, `TurnResult` models per `backend.md` §5.4.
      **Field order is load-bearing: scoring before question. Do not reorder**
- [ ] **4.5** Question similarity check against all prior questions, threshold
      from `app/core/heuristics.py`. Regenerate once naming the prior questions
- [ ] **4.6** Token minting, `POST /api/candidates/{id}/approve`, reject route
- [ ] **4.7** `GET /api/interview/{token}` returning `current_question`, so a
      refresh resumes rather than restarts
- [ ] **4.8** `POST /api/interview/{token}/start`
- [ ] **4.9** `POST /api/interview/{token}/answer`, transcribe, score, update
      state, return next question or completion
- [ ] **4.10** Evaluation per §5.5. Sub-scores computed in Python from
      accumulated `AnswerScore` rows; the model writes narrative only
- [ ] **4.11** `GET /api/interview/{token}/result`
- [ ] **4.12** `test_plan_covers_rubric`, `test_no_repeat_questions`,
      `test_state_object_grows_correctly`
- [ ] **4.13** `app/core/errors.py`: every code in `backend.md` §9, mapped from
      exceptions. Prose messages, never a status code or provider name

**Done when** a full interview runs end to end from curl: post a job, apply
with an audio file, approve, start, submit six answers, get a result.

**This is the day-6 checkpoint.** The product works. It has no interface.

---

## Phase 5 · Design foundation · 1.5 days

- [x] **5.1** Token layer verified against `DESIGN.md`. Every value present,
      nothing invented
- [x] **5.2** Primitives: `Button` all four levels with every state, `TextField`,
      `TextArea`, `Select`, `TagInput`, `Chip`, `Spinner`, `Divider`
- [x] **5.3** `HRShell` with sidebar, `CandidateShell` centered. One nav item,
      no placeholders
- [x] **5.4** `PageHeader`, `Section`, `Card`, `Split`
- [x] **5.5** `EmptyState`, `ErrorState`, `LoadingState`, `Toast`, `Modal`
- [x] **5.6** `api.ts`: typed client, one error shape, all routes
- [x] **5.7** Focus states visible on every interactive element. Tab through the
      whole primitive set with the mouse untouched

**Done when** a scratch page renders every primitive in every state and 5.7
passes.

---

## Phase 6 · Interview screen · 2 days

The hardest surface. Built before anything else visual because it defines the
two components worth building carefully.

- [x] **6.1** `AudioLevelMeter` driven by real `AnalyserNode` input. No
      simulated waveform
- [x] **6.2** `VoiceRecorder`: `MediaRecorder`, permission handling, Chrome webm
      and Safari mp4, all five states from `screens.md` §6
- [x] **6.3** Silence detection, 3 seconds, caption in `caution`
- [x] **6.4** Interview stage 1, ready screen
- [x] **6.5** Stage 2, question. `display` type, progress track not a stepper,
      auto-record on render or TTS end
- [x] **6.6** `speechSynthesis` playback with question text always visible
- [x] **6.7** Stage 3, processing. Labels change on real backend stage
      transitions only. `aria-live="polite"`. Previous question stays dimmed so
      the screen never goes blank
- [x] **6.8** Stage 4, transition. 320ms, 8px rise, instant under reduced motion
- [x] **6.9** Error states: transcription failure re-records in the same slot,
      connection loss auto-retries, invalid token full-region
- [x] **6.10** Refresh mid-interview resumes at the correct question
- [x] **6.11** Verified at 375px

**Done when** a full interview can be completed in the browser, and a mid-way
refresh resumes correctly.

---

## Phase 7 · Application screen · 1.5 days

- [ ] **7.1** `/apply/:jobId`, reusing `VoiceRecorder` and `AudioLevelMeter`
- [ ] **7.1b** `FileDropzone`: drag and drop, PDF only, 5MB, all four states
      from `screens.md` §6
- [ ] **7.2** Name and email with blur validation
- [ ] **7.3** Submit states: `Uploading`, `Reading your resume`,
      `Transcribing your introduction`
- [ ] **7.4** Short-recording warning under 20 seconds, warn not block
- [ ] **7.5** Permission-denied recovery block
- [ ] **7.6** `/apply/:jobId/done`

**Done when** a candidate can apply and the row appears screened in the
database.

---

## Phase 8 · HR screens · 2.5 days

- [ ] **8.1** Create Job, three stages: form, `Analyzing job description`,
      rubric reveal with `CopyLinkField`
- [ ] **8.2** `RubricPanel`, reused collapsed on Job Detail
- [ ] **8.3** Jobs Dashboard with empty state. `analyzing` rows not clickable
- [ ] **8.4** `DataTable`, `ScoreInline`, `RecommendationChip`, `StatusChip`.
      One tinted element per row
- [ ] **8.5** Job Detail: stat row as text not boxes, filter tabs, ranked table,
      empty state
- [ ] **8.6** `ScoreHero`, `ScoreBreakdown` with neutral bars
- [ ] **8.7** Candidate Detail split layout, `AudioPlayer`, collapsed
      transcript, resume panel with open link and collapsed extracted text,
      `EvidenceList` with source tags, conflicts panel when non-empty, approve
      and reject with confirmation modal, post-approval link state
- [ ] **8.8** Interview Result: one hero score, three sub-scores, strengths and
      concerns, transcript with per-turn criteria labels and response times
- [ ] **8.9** Compact layouts: tables become stacked cards under 768px

**Done when** the full flow is clickable start to finish with no curl.

---

## Phase 9 · Landing and completion · 0.5 days

- [ ] **9.1** Landing per `screens.md` §0. One accent element, no cards
- [ ] **9.2** `/interview/:token/done`. No score, no CTA. Reopening a completed
      link lands here rather than erroring

---

## Phase 10 · Hardening and handoff · 1.5 days

- [ ] **10.1** `app/cassettes.py`. Gemini keyed on stage plus input hash,
      transcription on audio hash, Supabase rows for the golden job
- [ ] **10.2** `tests/record_cassettes.py`, recorded against a real end-to-end
      run
- [ ] **10.3** **`DEMO_MODE=1` verified with the network physically
      disconnected.** A cassette miss raises loudly rather than calling out
- [ ] **10.4** Synthetic candidate harness per `backend.md` §11, run against a
      strong persona and a vague one
- [ ] **10.5** Screen review checklist from `design-system.md` §23 against all
      nine screens
- [ ] **10.6** README verified by following it on a clean checkout
- [ ] **10.7** Demo checklist in `PROJECT.md` run once, start to finish

**Done when** 10.3 passes. Everything else can be fixed live; a rate-limited
demo cannot.

---

## Notes

**Do not build ahead of the specs.** If a screen needs something
`screens.md` does not describe, the spec is wrong and gets updated first.
Improvising in code produces inconsistency that is expensive to unwind later.

**Do not start Phase 5 before 3.9 passes.** Score consistency is the load
bearing property of this product. A beautiful interface over drifting scores is
worth less than a plain one over stable scores.

**The three open client questions** in `PROJECT.md` block parts of Phase 6.
Send them before Phase 4 ends.

**Prior art reviewed** for the backend is documented in `docs/prior-art.md`,
including what was adopted and what was deliberately rejected.

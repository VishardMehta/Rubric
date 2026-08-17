# Prior art

Open-source projects reviewed before specifying Rubric, what was taken from
each, and what was deliberately not taken.

Reviewed August 2026.

---

## Reviewed

| Project | License | Language | Relevance |
|---|---|---|---|
| [ngoanpv/DeepInterview](https://github.com/ngoanpv/DeepInterview) | Apache-2.0 | Python | Closest architectural match. Question planner, per-question rubrics, competency scorecard |
| [IliaLarchenko/Interviewer](https://github.com/IliaLarchenko/Interviewer) | Apache-2.0 | Python | Synthetic candidate plus interviewer-grading test harness |
| [adrianhajdin/ai_mock_interviews](https://github.com/adrianhajdin/ai_mock_interviews) | see repo | TypeScript | Gemini scoring across named categories. Well documented |
| [g0da-s/AI-Interview-Simulator](https://github.com/g0da-s/AI-Interview-Simulator) | none stated | Python | Jinja2 prompt templates, prompt version file |
| [Ajuu1801/Smart-Recruitment-System](https://github.com/Ajuu1801/Smart-Recruitment-System-AI-Powered-Hiring-Platform) | see repo | Python, React | HR-side screening and ranking |

Note that almost all open-source work in this space is **candidate-side
interview practice**, not HR-side hiring. The HR-side projects do resume
screening but no voice interviewing. Nothing open-source does both halves,
which is why Rubric is specified rather than assembled.

---

## Adopted

### Per-answer incremental scoring
**From** DeepInterview, `packages/shared/schema/PlannedQuestion.json`

Their `PlannedQuestion` carries its own `rubric` array rather than only a
pointer to interview-level criteria, so each answer is scored against that
question's criteria as it arrives.

Rubric adopts the pattern in `backend.md` §5.4: answers are scored inside the
turn call that was happening anyway. Final evaluation drops from 10 to 25
seconds to roughly 5, each score anchors to the single answer that produced it,
and it costs no extra request.

### Evidence must be a quote
**From** DeepInterview, `apps/agent/src/deepinterview_agent/post/prompts.py`

Their assessor prompt requires concrete evidence cited from the answer, and
their `CompetencyScore` schema makes `evidence` a required field.

Rubric adopts this in `backend.md` §5.2 and §5.4, and goes one step further:
the evidence string is validated to appear in the transcript after whitespace
normalisation. A paraphrase means the model invented support for a score it had
already decided on.

### Explicit unanswered-question handling
**From** DeepInterview, `evaluate_answer_prompts`

Their prompt has a branch for when no answer exists, asking for a low,
evidence-light score rather than letting the model guess. Rubric handles the
same case when transcription fails and the candidate declines to re-record.

### Prompt builders, not string constants
**From** DeepInterview, `post/prompts.py`

Prompts are functions returning a `(system, user)` tuple, composing state into
a compact block. A prompt you cannot call with fixture inputs is a prompt you
cannot test. `backend.md` §5.6.

### Synthetic candidate and interviewer grading
**From** IliaLarchenko/Interviewer, `tests/testing_prompts.py`

They run a scripted model as the candidate, then grade the **interviewer**
against named criteria including whether it repeated questions already
answered.

This is the only way to test an adaptive interviewer without human subjects.
Rubric adopts it in `backend.md` §11 with criteria specific to this product:
no repeats, rubric coverage, anchoring to real claims, depth progression, and
not leaking the expected answer.

---

## Deliberately not adopted

| Not taken | From | Why |
|---|---|---|
| LangGraph `StateGraph` | DeepInterview | Banned in `CLAUDE.md`, and overkill for five sequential calls. The state object in `product.md` §6 is a dict passed forward, which is all that is needed |
| LiveKit real-time voice | DeepInterview | Rubric is turn-based. Real-time streaming adds infrastructure for latency the product does not need |
| Multilingual question text | DeepInterview | Their `text` is a locale map. Rubric is English only |
| Coding round section | DeepInterview | Rubric has no code execution |
| Fractional criterion weights | DeepInterview | Their weights are floats. Rubric uses integer points summing to exactly 100, which is legible to HR and validates cleanly |
| `model_answers` in the result | DeepInterview | Coaching output for a candidate-practice product. Rubric is HR-side and the candidate never sees their result |
| Adversarial score verification | DeepInterview, `verify_score_prompts` | A second pass verifying the first score. Genuinely improves consistency but doubles requests, which matters on a free tier. Revisit if the consistency harness shows drift the sub-score discipline cannot fix |
| Jinja2 prompt templates | AI-Interview-Simulator | No license stated on that repo, so nothing is copied from it. The prompt-version file is a good idea worth reimplementing independently if prompts start churning |
| Vapi voice agent | ai_mock_interviews | Paid |

---

## Attribution

DeepInterview and Interviewer are Apache-2.0. Rubric copies no source from
either; both influenced design decisions listed above. If any source is later
copied verbatim, add the Apache-2.0 notice and attribution to a `NOTICE` file
at the repository root at that time.

Nothing is copied from AI-Interview-Simulator, which states no license.

---

## Third-party behaviour recorded during hardening

Not prior art in the sense above: nothing here was adopted. These are two
behaviours of libraries this project depends on, found by reading their
source while debugging, and written down because in both cases the symptom
pointed somewhere other than the cause.

### `postgrest-py` hardcodes HTTP/2 with no retry

`postgrest` builds its own `httpx.Client` with `http2=True` fixed in the
constructor. httpx keeps HTTP/2 connections pooled; Supabase's edge closes
them when idle. httpx then writes a request onto a connection the server
has already closed and httpcore raises
`RemoteProtocolError("Server disconnected")`, which it will not retry
because the request was already sent.

Supabase's Python client accepts `ClientOptions(httpx_client=...)`, so the
fix is to pass a client configured deliberately rather than to patch or
replace the library. See `SUPABASE_*` in `app/core/heuristics.py`.

### Starlette's catch-all exception handler runs outside `CORSMiddleware`

`@app.exception_handler(Exception)` is installed in `ServerErrorMiddleware`,
which sits outside the middleware stack the application adds. A 500
generated there does not pass back through `CORSMiddleware`, so it carries
no `Access-Control-Allow-Origin` header and the browser blocks a response
the server genuinely sent. The frontend sees `fetch` throw and reports a
network failure for a backend that is up and answering.

Confirmed by measurement rather than by reading alone: `/api/health` 200
with the header present, a handled 503 with the header present, an
unhandled 500 with it missing. The handler now echoes the request origin
when it is in the configured allowlist. See `_allow_origin` in
`app/core/errors.py`.

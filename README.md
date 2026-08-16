# Rubric

Rubric reads a job description, builds a scoring rubric, and screens every
resume and voice introduction against it.

HR posts a job. Rubric extracts the criteria and assigns point allocations
summing to 100. Candidates apply with a resume and a two minute spoken
introduction. The rubric is scored twice, once from the resume and once from
the introduction, and the two are weighted 60/40 into one screening score,
with every point backed by a quote copied from its own source. HR reviews the
ranked list and approves who moves forward. Approved candidates take a voice
interview of exactly 10 questions, six or seven planned from their resume and
the rubric and three or four written live from what they actually said, then
the interview is evaluated against the same rubric.

Localhost demo. No deployment.

---

## Architecture

```
Browser                    FastAPI                    Outside the process
────────────────────────────────────────────────────────────────────────
React + Vite  ──HTTP──▶  api/          routes
   :5273                 services/     rubric, screening, interview, scoring
                         integrations/ ──▶ Gemini      structured JSON
                              │             Groq        speech to text
                              │             Supabase    Postgres + storage
                              ▼
                         models.py     Pydantic schemas, shared by both
```

Five things decide how this behaves:

**The rubric is the contract.** Stage 1 turns a job description into 4 to 7
criteria whose points total exactly 100. Every score after that is computed
against those criteria and nothing else. No holistic judgement.

**Nothing emits a bare total.** Every scoring stage returns per-criterion
sub-scores, each with a quote copied verbatim from the source it claims, and
Python verifies the sum before the row is saved. A mismatch is a validation
failure, not a rounding detail. The same transcript scored twice drifts 15 to
20 points if you ask for one number; anchored sub-scores hold steady.

**Validation is code, not prompting.** Every LLM call goes through
`generate_structured(system, user, Model, validate=...)`. A violation raises
with a message written as retry guidance, the call is retried once, and a
second failure is a real error. Nothing is ever silently repaired: a rubric
quietly adjusted to sum to 100 no longer matches the reasoning that produced
it.

**The interview carries state.** A plan is generated once, before question
one, from the resume, the job and the rubric; it fixes what all 10 slots are
for and which are follow-ups. Each turn then scores the answer, extracts the
concrete claims in it, and only then writes the next question. That ordering
is why a follow-up can say "how did you handle the cold start problem there?"
instead of "tell me about system design".

**The frontend never derives a score.** Bands, recommendations and weights are
computed server side and sent already resolved. Thresholds change, and
frontend logic that duplicates them drifts until the two disagree in front of
a client.

Deeper detail: `docs/backend.md` (schema, API, LLM stages), `docs/product.md`
(states, routes), `docs/screens.md`, `docs/design-system.md`.

### Stack

| Need | Choice |
|---|---|
| LLM | Gemini Flash, free tier, structured output |
| Speech to text | Groq `whisper-large-v3-turbo`, free tier |
| Fallback | `faster-whisper` base, local CPU |
| Text to speech | `window.speechSynthesis`, browser native, no API |
| Audio capture | Native `MediaRecorder`, no packages |
| Database | Supabase Postgres, `service_role` from the backend only |
| Backend | FastAPI, Pydantic v2, synchronous |
| Frontend | React 19, Vite, plain CSS with a token layer |

Everything is free tier. There are no paid API calls anywhere, including
during development.

---

## Setup

Requires **Python 3.11+**, **Node 20+**, and **ffmpeg** for the offline
transcription fallback.

```bash
brew install ffmpeg          # macOS. apt install ffmpeg on Debian/Ubuntu
```

**1. Install**

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd ../frontend && npm install
```

`[dev]` adds pytest and ruff. Drop it if you only want to run the app.

**2. Get the keys** — all three are free, no card required.

| Variable | Where | How |
|---|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Sign in with Google, "Create API key". Free tier is enough |
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) | Sign up, "Create API Key". Optional: without it the local Whisper model is used instead, just slower |
| `SUPABASE_URL` | [supabase.com/dashboard](https://supabase.com/dashboard) | New project, then Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Same page | Under Project API keys, the `service_role` key |

`service_role` bypasses row level security. It belongs in `backend/.env` and
nowhere else — never the frontend, never committed. `.env` is gitignored;
`.env.example` holds variable names with empty values and never a real one.

```bash
cp backend/.env.example backend/.env    # then fill it in
```

**3. Create the database.** In the Supabase SQL editor, run these in order:

| File | What it does |
|---|---|
| `database/schema.sql` | Five tables, row level security, three private storage buckets |
| `database/002_accounts.sql` | HR accounts and sessions, job ownership, two atomicity functions |
| `database/003_screening_components.sql` | The resume and voice score columns |

All three are additive and safe to re-run. You now have an empty database.

**4. Run**

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8123
cd frontend && npm run dev
```

Open **http://localhost:5273**, register an account, post a job, then apply to
it from `/apply` in another browser profile.

Both ports are pinned. Vite uses `strictPort` on 5273 so it cannot drift and
silently fall outside the backend's CORS list. Override the API base with
`VITE_API_BASE_URL` if you need to.

> Free Supabase projects pause after about seven days idle and need a manual
> restore from the dashboard. A paused project looks exactly like a broken
> application, so check this first when something stops working.

---

## Your data is yours

Everyone who runs this creates **their own Supabase project** and puts their
own keys in their own `backend/.env`, which is gitignored and never leaves
their machine. Running the three SQL files gives them an empty database that
nobody else can reach.

Nothing in this repository points at a database. There is no shared instance,
no seeded candidates, and no credentials in any tracked file. Two people
running Rubric are running two entirely separate systems.

The one thing to be careful about: if you ever paste your `SUPABASE_URL` and
`service_role` key somewhere shared, that key is a god key over your project.
Rotate it in the dashboard if it leaks.

---

## Demo mode

Free tiers rate-limit, and a 429 during a live demo is unrecoverable in the
moment.

```bash
DEMO_MODE=1 .venv/bin/uvicorn app.main:app --port 8123
```

Replays recorded responses for one golden job and candidate instead of calling
Gemini, Groq or Supabase. The whole product runs from
`backend/tests/cassettes/` with no keys and no network.

Verify that rather than trusting it:

```bash
cd backend && .venv/bin/python -m pytest tests/test_demo_mode.py -q
```

Those tests disable IP networking inside the process, then drive the full flow
over HTTP. A cassette miss raises `cassette_miss` and never falls through to a
network call — a demo mode that quietly reaches for the internet would still
get rate limited during the demo it exists to protect.

Re-record after changing any prompt. A prompt edit changes the cassette key,
so a stale recording misses loudly instead of replaying the answer to a
question no longer being asked:

```bash
cd backend && .venv/bin/python -m tests.record_cassettes
```

`DEMO_AUTH=1` is separate: it makes any email and any password sign in,
creating the account on the spot. It is a real authentication bypass, so it is
loud — a warning on every boot and every sign in, `demo_auth` on
`GET /api/health`, and a notice on the sign in screen itself. The test suite
pins it off, so the real login path is always what is tested.

---

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check .
cd frontend && npx tsc --noEmit && npx eslint src --max-warnings 0 && npm run build
```

Tests never assert on model prose, only on structural invariants: sub-scores
sum to their total, every cited criterion exists in the rubric, no question
repeats a prior one.

Two harnesses make real API calls, so they run on demand rather than in CI:

```bash
cd backend
.venv/bin/python -m tests.consistency_harness              # score stability
.venv/bin/python -m tests.synthetic_candidate --persona vague
```

`consistency_harness` scores one transcript five times and fails if the range
exceeds the threshold in `app/core/heuristics.py`. There is no ground truth
for a screening score, so variance is the only measurable property — and it is
the one that decides whether re-running a candidate in front of a client gives
the same number.

`synthetic_candidate` plays a full interview against a scripted persona and
grades the **interviewer** on repeats, coverage, anchoring and answer leaking.
Use the `vague` persona: a strong candidate makes any interviewer look good,
while one who answers everything with "we used best practices" is what exposes
a reactive interviewer looping or drifting.

---

## Layout

```
backend/app/
  api/            HTTP routes, one module per resource
  core/           settings, the one error shape, every tuned threshold
  integrations/   Gemini, Groq, Supabase, pypdf. Anything outside the process
  services/       Rubric's own logic: rubric, screening, interview, scoring
  models.py       Pydantic models shared across all of the above

frontend/src/
  api/            the typed client. Every network call goes through here
  hooks/          stateful React hooks
  lib/            stateless helpers: formatting, thresholds, tone mapping
  components/
    primitives/   generic controls that know nothing about hiring
    layout/       shells, page header, card, split
    feedback/     empty, error, loading, toast, modal
    data/         scores, chips, tables
    domain/       the voice pipeline and other Rubric-specific pieces
  routes/
    candidate/    apply, portal, interview
    hr/           the dashboard and everything under it
  styles/         tokens.css and base.css
```

---

## Known limits

Stated rather than discovered.

- **Registration is open and there is no password reset.** Both need email
  delivery, which is out of scope: an invitation or a reset link has nowhere
  to go.
- **Candidates have no server-side accounts.** `/candidate/signin` records an
  address in `localStorage` so the portal can show someone their applications
  without asking them to retype it. `GET /api/applications?email=` is an open
  lookup, which is exactly why nothing it returns carries a score.
- **The HR session token lives in `localStorage`**, so any script on the page
  could read it. There are no third-party scripts here, which is what makes
  that acceptable; it would not be on a deployed build.
- **Candidates never see a score**, at any point, including on completion.
- **In `DEMO_MODE` a new recording cannot be transcribed** — only the golden
  audio is in the cassettes.
- **Rubric regeneration does not rescore candidates already screened.**

This is an academic demonstration and is not intended for screening real
candidates.

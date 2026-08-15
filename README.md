# Rubric

Rubric reads a job description, builds a scoring rubric, and screens every
resume and voice introduction against it.

HR posts a job. Rubric extracts the criteria and assigns point allocations
summing to 100. Candidates apply with a resume and a two minute spoken
introduction. The resume text is extracted, the introduction is transcribed,
and both are scored against the same rubric criterion by criterion, with every
piece of evidence tagged by which source it came from. HR reviews the ranked
list and approves who moves forward. Approved candidates take a voice interview
of 5 to 10 adaptive questions that follow what they actually said, then the
interview is evaluated against the same rubric.

Localhost demo. No deployment.

---

## Before running anything

**Un-pause the Supabase project.** Free projects pause after about seven days
of inactivity and need a manual restore from the dashboard. A paused project
looks exactly like a broken application.

---

## Setup

Requires Python 3.11+, Node 20+, and `ffmpeg` for the offline transcription
fallback.

```bash
brew install ffmpeg
```

Backend:

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -e .
```

Frontend:

```bash
cd frontend && npm install
```

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase project settings, API |
| `SUPABASE_SERVICE_ROLE_KEY` | Same page. Backend only, never the frontend |
| `GEMINI_API_KEY` | aistudio.google.com, free tier |
| `GROQ_API_KEY` | console.groq.com, free tier |

Run `database/schema.sql` in the Supabase SQL editor. It creates the five
tables, enables row level security, and creates the three private storage
buckets (`introductions`, `answers`, `resumes`).

Then run `database/002_accounts.sql`. It adds HR accounts and sessions, gives
jobs an owner, and adds the two Postgres functions that make registration and
candidate approval atomic. It is additive and safe to re-run.

Optionally run `database/seed.sql` after those for demo data: two jobs, five
applications and one completed interview, enough to open every screen with
something on it. The scores and transcripts in that file are written by hand
rather than produced by Gemini and Groq, so it is a way to see the UI, not a
way to see the pipeline. Re-running it is a no-op.

Run it **before** you register your first account. Seeded jobs have no owner,
and the first account claims every ownerless job; seed afterwards and the new
rows stay invisible until you assign them by hand. The SQL to do that is in a
comment at the top of `database/002_accounts.sql`.

## Running

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8123
```

```bash
cd frontend && npm run dev
```

Open http://localhost:5273

Both ports are pinned. The Vite dev server uses `strictPort` on 5273 so it
never drifts to 5174 and silently falls outside the backend's CORS list, and
the frontend defaults to `127.0.0.1:8123` for the API. Override that with
`VITE_API_BASE_URL` if you need a different one.

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
    candidate/    unauthenticated: apply and interview
    hr/           the dashboard and everything under it
    dev/          the primitives gallery, DEV builds only
  styles/         tokens.css and base.css
```

## Demo mode

Free tiers rate-limit, and a 429 during a live demo is unrecoverable in the
moment.

```bash
DEMO_MODE=1 .venv/bin/uvicorn app.main:app --port 8123
```

Replays recorded responses for the golden job and candidate instead of calling
Gemini, Groq or Supabase. The whole product runs from `backend/tests/cassettes/`
with no keys and no network.

Verify that claim rather than trusting it:

```bash
cd backend && .venv/bin/python -m pytest tests/test_demo_mode.py -q
```

Those tests disable IP networking inside the process and then drive the full
demo flow over HTTP. A cassette miss raises `cassette_miss` and never falls
through to a network call, which is the entire point: a demo mode that quietly
reaches for the internet would still get rate limited during the demo it exists
to protect.

Re-record after changing any prompt. A prompt edit changes the cassette key, so
a stale recording misses loudly instead of replaying the answer to a question
that is no longer being asked:

```bash
cd backend && .venv/bin/python -m tests.record_cassettes
```

## Harnesses

Both make real API calls, so they run on demand rather than in CI.

```bash
cd backend
.venv/bin/python -m tests.consistency_harness              # score stability
.venv/bin/python -m tests.synthetic_candidate --persona vague
```

`consistency_harness` scores one transcript five times and fails if the range
exceeds the threshold in `app/core/heuristics.py`. There is no ground truth for
a screening score, so variance is the only measurable property, and it is the
one that decides whether re-running a candidate in front of a client produces
the same number. Run it after any change to the screening prompt.

`synthetic_candidate` plays a full interview against a scripted persona, then
grades the **interviewer** on repeats, coverage, anchoring, progression and
answer leaking. Run the `vague` persona: a strong candidate makes any
interviewer look good, while a candidate who answers everything with "we used
best practices" is what makes a reactive interviewer loop or drift.

## Documentation

| Document | Contents |
|---|---|
| `CLAUDE.md` | Engineering constraints |
| `DESIGN.md` | Design tokens |
| `docs/design-system.md` | Components, states, application rules |
| `docs/product.md` | Product structure, states, routes, interview plan |
| `docs/screens.md` | Ten screen specifications |
| `docs/backend.md` | Schema, API, LLM stages, validation, tests |
| `docs/implementation-plan.md` | Sequential build plan |
| `docs/prior-art.md` | Open-source projects reviewed and what was adopted |
| `PROJECT.md` | Scope, timeline, open questions |

## Notes

HR signs in with an email and a password, and sees only the roles they posted
and the applicants to those roles. The first account you register claims every
job that already existed, including everything from `database/seed.sql`.

Registration is open to anyone who can reach the page, and there is no password
reset. Both follow from email delivery being out of scope: an invitation or a
reset link has nowhere to go. On a localhost demo that is the right trade, but
it is a stated one rather than an accident.

### Demo sign in

`DEMO_AUTH=1` in `backend/.env` makes any email and any password sign in,
creating the account on the spot, and makes the candidate portal fall back
to showing every application when the address it is given has none. It is
for walking someone through the product without stopping to remember a
password.

It is a real authentication bypass, so it is loud about it: the backend
logs a warning on every boot and on every sign in, `GET /api/health`
reports `demo_auth`, and the sign in screen says so on the page. Turn it off
with `DEMO_AUTH=0`.

It is separate from `DEMO_MODE`, which swaps the database for an in-memory
store. The test suite pins it off, so the real login path is always what is
tested.

The session token is kept in `localStorage`, so any script running on the page
could read it. There are no third-party scripts here, which is what makes that
acceptable; it would not be on a deployed build.

Candidates never see their own scores, and the candidate side has no accounts
at all. Roles are public, and an interview link is an opaque 256-bit token.

Candidates track their applications by entering the email they applied with,
at `/apply` under My applications. An interview invitation appears there once
HR approves them. Anyone who knows an email address can see the roles that
address applied to and the status of each; the response carries no score,
band, recommendation or assessment, which is what makes that acceptable on a
localhost demo. There is no candidate password, because a reset flow would
need email delivery.

This is an academic demonstration and is not intended for screening real
candidates.

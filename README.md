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

Run `database/schema.sql` in the Supabase SQL editor, then create three private
storage buckets: `introductions`, `answers` and `resumes`.

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
Gemini, Groq or Supabase. Verify it works with the network disconnected before
any client demo.

Re-record after changing a prompt:

```bash
cd backend && .venv/bin/python -m tests.record_cassettes
```

## Documentation

| Document | Contents |
|---|---|
| `CLAUDE.md` | Engineering constraints |
| `DESIGN.md` | Design tokens |
| `docs/design-system.md` | Components, states, application rules |
| `docs/product.md` | Product structure, states, routes, interview plan |
| `docs/screens.md` | Nine screen specifications |
| `docs/backend.md` | Schema, API, LLM stages, validation, tests |
| `docs/implementation-plan.md` | Sequential build plan |
| `docs/prior-art.md` | Open-source projects reviewed and what was adopted |
| `PROJECT.md` | Scope, timeline, open questions |

## Notes

There is no HR authentication. This is a deliberate decision for a localhost
demo, not an oversight.

Candidates never see their own scores.

This is an academic demonstration and is not intended for screening real
candidates.

# Rubric backend specification

FastAPI, Supabase, Gemini, Groq Whisper. Free tier throughout.

This document is the implementation source of truth for the backend. Where it
disagrees with `PROJECT.md`, this document wins.

---

## 1. Architecture

```
React (Vite)                    FastAPI                     External
─────────────                   ───────                     ────────
                                                            
apply page ──resume pdf──▶  POST /apply
           ──audio blob──▶       │
                                  ├──▶ Supabase Storage  (resume + audio)
                                  ├──▶ pypdf             (resume text)
                                  ├──▶ Groq Whisper      (transcript)
                                  ├──▶ Gemini            (screening, both sources)
                                  └──▶ Supabase DB       (candidate row)

interview  ──audio blob──▶  POST /interview/{token}/answer
                                  │
                                  ├──▶ Supabase Storage
                                  ├──▶ Groq Whisper
                                  ├──▶ Gemini            (next question)
                                  └──▶ Supabase DB       (turn + state)

HR pages   ──────────────▶  GET  /jobs, /candidates, ...
                                  └──▶ Supabase DB
```

The frontend never talks to Supabase, Gemini or Groq. One boundary.

**Everything is synchronous.** No task queue, no background workers. Screening
takes 8 to 20 seconds and the request holds open for it. At demo scale this is
correct and it removes an entire category of failure. If a later phase needs
concurrency, that is when a queue earns its place.

---

## 2. Stack

| Layer | Choice |
|---|---|
| API | FastAPI, uvicorn |
| DB and storage | Supabase, `supabase-py`, `service_role` key |
| LLM | Gemini Flash via `google-genai`, structured output through `response_schema` |
| STT primary | Groq `whisper-large-v3-turbo` via the `groq` SDK |
| STT fallback | `faster-whisper`, `base` model, local, CPU |
| Resume text | `pypdf`, pure Python, MIT |
| Validation | Pydantic v2 |
| Tests | pytest |

Pin the exact Gemini model id in `config.py`, not inline at call sites. Verify
its current free-tier limits before the first client demo.

Not permitted: LangChain, LangGraph, Instructor, Celery, Redis, SQLAlchemy,
`openai-whisper`.

---

## 3. Schema

Supabase Postgres. This supersedes the draft in `PROJECT.md`.

The five tables below are `database/schema.sql`. HR accounts, job ownership
and the atomic operations were added afterwards in
`database/002_accounts.sql`, summarised in §3.1. `schema.sql` is not edited
retrospectively, so the two files together are the current schema and the
split records what was added when.

```sql
create extension if not exists "pgcrypto";

-- Jobs -------------------------------------------------------------------

create table jobs (
  id           uuid primary key default gen_random_uuid(),
  title        text not null,
  description  text not null,
  skills       text[] not null default '{}',
  experience   text,
  rubric       jsonb,                      -- see §5.1, null while analyzing
  state        text not null default 'analyzing',
  created_at   timestamptz not null default now(),
  constraint jobs_state_check
    check (state in ('analyzing', 'active', 'closed'))
);

-- Candidates -------------------------------------------------------------

create table candidates (
  id                uuid primary key default gen_random_uuid(),
  job_id            uuid not null references jobs(id) on delete cascade,
  name              text not null,
  email             text not null,
  audio_path        text,                  -- storage object path, not a URL
  transcript        text,
  resume_path       text,                  -- storage object path
  resume_text       text,                  -- extracted, see §7.1
  screening_score   int,                   -- 0 to 100
  screening_band    text,                  -- strong | borderline | weak
  sub_scores        jsonb,                 -- see §5.2
  matched_skills    text[] not null default '{}',
  unevidenced_skills text[] not null default '{}',
  assessment        text,                  -- prose reasoning
  recommendation    text,                  -- shortlist | review | reject
  state             text not null default 'applied',
  created_at        timestamptz not null default now(),
  constraint candidates_state_check
    check (state in ('applied','screening','screened','approved',
                     'rejected','interviewing','interviewed')),
  constraint candidates_score_range
    check (screening_score is null or screening_score between 0 and 100)
);

create index candidates_job_score_idx
  on candidates (job_id, screening_score desc nulls last);

-- Interviews -------------------------------------------------------------

create table interviews (
  id              uuid primary key default gen_random_uuid(),
  candidate_id    uuid not null unique references candidates(id) on delete cascade,
  token           text not null unique,
  plan            jsonb,                   -- see §5.3
  state_object    jsonb not null default '{}'::jsonb,  -- see §6
  total_questions int,
  status          text not null default 'not_started',
  started_at      timestamptz,
  completed_at    timestamptz,
  created_at      timestamptz not null default now(),
  constraint interviews_status_check
    check (status in ('not_started','in_progress','complete','evaluated'))
);

create index interviews_token_idx on interviews (token);

-- Turns ------------------------------------------------------------------

create table interview_turns (
  id                    uuid primary key default gen_random_uuid(),
  interview_id          uuid not null references interviews(id) on delete cascade,
  slot                  int not null,      -- 1-indexed
  question              text not null,
  criterion_ids         text[] not null default '{}',
  answer_text           text,
  answer_audio_path     text,
  response_time_seconds int,
  asked_at              timestamptz not null default now(),
  answered_at           timestamptz,
  unique (interview_id, slot)
);

-- Results ----------------------------------------------------------------

create table interview_results (
  interview_id    uuid primary key references interviews(id) on delete cascade,
  overall_score   int not null,
  technical_score int not null,
  communication_score int not null,
  experience_score int not null,
  band            text not null,
  strengths       text[] not null default '{}',
  concerns        text[] not null default '{}',
  recommendation  text not null,
  created_at      timestamptz not null default now()
);
```

**Storage buckets**

| Bucket | Contents | Access |
|---|---|---|
| `introductions` | Voice introduction audio | Private. Backend issues signed URLs |
| `answers` | Interview answer audio | Private. Backend issues signed URLs |
| `resumes` | Uploaded resume PDFs | Private. Backend issues signed URLs |

Store the object **path** in the database, never a URL. URLs expire; paths do
not. The API resolves a path to a signed URL at response time.

**RLS** Leave enabled. The backend uses `service_role` and bypasses it. The
frontend has no Supabase credentials at all.

### 3.1 Accounts and ownership

`database/002_accounts.sql`, added after the MVP shipped. Additive only.

```sql
create table hr_users (
  id            uuid primary key default gen_random_uuid(),
  email         text not null unique,     -- stored lowercased
  name          text not null,
  company       text,
  password_hash text not null,            -- scrypt, hex
  password_salt text not null,            -- 16 random bytes, hex
  created_at    timestamptz not null default now()
);

create table hr_sessions (
  token      text primary key,            -- secrets.token_urlsafe(32)
  hr_user_id uuid not null references hr_users(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

alter table jobs add column owner_id uuid references hr_users(id) on delete cascade;
```

`owner_id` is nullable because rows created before accounts existed have no
owner. The first account registered claims all of them, inside the same
transaction as its own insert.

Passwords use `hashlib.scrypt` from the standard library. CLAUDE.md forbids
adding a dependency without asking, and bcrypt or argon2 would be one. Cost
parameters are named in `app/core/heuristics.py`. Sessions are opaque tokens
in a table rather than JWTs, because a JWT cannot be revoked without a
server-side list, at which point it is a session table with extra steps.

**Atomic operations.** PostgREST cannot run a multi-statement transaction and
the supabase python client exposes no transaction API, so anything that must
be all-or-nothing is a Postgres function called through `client.rpc()`:

| Function | Why it cannot be separate calls |
|---|---|
| `register_hr_user` | The insert and the ownerless-job claim must both happen or neither. A partial run leaves a registered user whose jobs are orphaned with no route back to them |
| `approve_candidate_atomic` | Read, insert, update used to interleave on a double click: both calls saw no interview, both inserted, and the loser hit the `interviews.candidate_id` unique constraint and surfaced as a 500 |

`POST /jobs` and `POST /apply` are deliberately **not** atomic. Both have a
model call in the middle, and both leave a recoverable partial state on
purpose so nothing the user or the candidate did is lost.

The in-memory demo store (`app/integrations/demo_supabase.py`) implements
both functions again in Python. That duplication is the price of DEMO_MODE
running the real storage layer instead of stubbing it; the demo-mode tests
assert on the behavior that separates them, so a drift fails a test.

---

## 4. API

All routes are prefixed `/api`. All responses are JSON. Errors follow §9.

**Authentication.** Every HR route requires `Authorization: Bearer <token>`
and answers `401 not_authenticated` without one. Every candidate route, and
`/health`, is public. Enforcement is a per-route FastAPI dependency
(`app/core/auth.py`), not middleware: the candidate side is public by design,
and a middleware allowlist that drifts either locks a candidate out of their
interview or exposes HR's data, with neither failure visible from the route
it affects.

**Ownership.** On top of the session, every HR route checks that the job, or
the candidate's job, belongs to the signed-in account. Someone else's row
answers 404, never 403, so the route cannot be used to discover which ids
exist under other accounts. `app/api/jobs.owned_job_or_404` and
`app/api/candidates.owned_candidate_or_404` are the only two gates; a route
that reads `storage.get_job` or `storage.get_candidate` directly is how an
IDOR gets in.

### Job description parsing

`POST /jobs/description-document` returns `{text, facts}`. `facts` is a
`JobFacts` object, or null when parsing failed.

Every field except `skills` and `description` is nullable, and the prompt is
told to return null rather than guess. Verified against the two PDFs in
`Demofiles/`: neither states pay, and both return `compensation: null`
rather than a range inferred from the seniority. A named office location
alone does not produce `workplace_type`, because plenty of onsite-sounding
roles are hybrid and the document has not said.

Parsing failure is not an error. The raw text is still returned, which is
exactly what this endpoint did before parsing existed, so a rate limited
model degrades to the old behavior instead of blocking HR from posting a
role.

### Candidate portal

`GET /applications?email=` is unauthenticated and returns every application
from one email address. There are no candidate accounts: a password would
need a reset flow, which would need email delivery, which is out of scope.

**It must never carry a score.** The candidate never sees one, at any point
(product.md section 2), and this is the only candidate-facing response
built from a candidate row, which holds `screening_score`,
`screening_band`, `recommendation`, `sub_scores` and `assessment`. The
response is assembled field by field from a whitelist, never by spreading a
row or reusing an HR model, and `tests/test_applications.py` asserts on the
serialized payload so a field added to the model fails there even if it
type checks.

The internal candidate state is collapsed to a coarser candidate-facing
vocabulary: `rejected` and `screened` are words for the hiring team. A
rejected application reads as `closed` and says nothing about why.

`interviews.invited_at` separates approving from sending. The portal
surfaces a link only once HR has actually invited them, and withdraws it
once the interview is complete so a finished link cannot be reopened.

**Known and accepted:** anyone who knows an email can see the roles that
address applied to and the status of each. It carries no score, and it is
recorded in the README next to the other stated limits.

### Resume profile

`candidates.resume_profile jsonb`, added in `database/002_accounts.sql`.
Built by one Gemini call inside `POST /apply`, after resume extraction and
before screening.

**Display only.** Screening reads the raw resume text against the rubric and
remains the only stage that produces a number. Summarising first and scoring
the summary would put a lossy step between the evidence and the score, and
the evidence quotes on Candidate Detail are checked against the original
text.

**Never fatal.** A failure leaves the column null and the application
completes. The candidate has just recorded a two minute introduction;
losing that because a display convenience failed would be absurd. Candidate
Detail falls back to the raw `resume_text` disclosure it has always shown.
`POST /candidates/{id}/reparse-resume` retries it later, mirroring
`rescreen`, and unlike rescreen it cannot change any score.

**Nothing is inferred.** Dates, grades and titles are copied as the resume
writes them. A computed graduation year is indistinguishable from a stated
one, and this is attached to a named person. Course projects are kept out of
the work history and left in the resume text where screening reads them.

One validator earns its place: a link must be a real URL. Observed on a real
resume, a PDF hyperlink whose anchor text was "Kaggle" extracted as the bare
word and came back as a link, which would render as an anchor to nowhere.
The model is told to correct it rather than the value being dropped
silently.

### Accounts

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/register` | Create an account, sign in, claim ownerless jobs if first. Returns the token |
| `POST` | `/auth/login` | Sign in. Returns the token |
| `POST` | `/auth/logout` | Delete the session. Succeeds even with a dead token |
| `GET` | `/auth/me` | The current account. Used to validate a stored token on load |

`/auth/login` returns the same error for an unknown email and a wrong
password, so it cannot be used to enumerate registered addresses.

### Jobs

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/jobs` | Create job. Runs rubric generation synchronously. Returns the job with its rubric |
| `GET` | `/jobs` | List jobs with applicant counts |
| `GET` | `/jobs/{job_id}` | Job with rubric and pipeline counts |
| `POST` | `/jobs/{job_id}/rubric/regenerate` | Rebuild the rubric |
| `GET` | `/jobs/{job_id}/candidates` | Ranked candidates, score descending |

`POST /jobs` request:

```json
{
  "title": "Senior Python Developer",
  "description": "...",
  "skills": ["Python", "Django", "PostgreSQL"],
  "experience": "2 to 4 years"
}
```

`GET /jobs/{id}/candidates` response item:

```json
{
  "id": "...",
  "name": "Priya Nair",
  "email": "priya@example.com",
  "screening_score": 84,
  "screening_band": "strong",
  "recommendation": "shortlist",
  "matched_count": 9,
  "skills_total": 11,
  "state": "interviewed"
}
```

The band is computed server-side and returned. The frontend never derives a
band from a number.

### Application

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/apply/{job_id}` | Public job summary for the apply page. Title only, never the rubric |
| `POST` | `/apply/{job_id}` | Multipart: `name`, `email`, `resume`, `audio`. Extracts, transcribes, screens, returns candidate id |

`POST /apply/{job_id}` runs: upload resume and audio, extract resume text,
transcribe audio, screen both against the rubric, insert. Sets
state to `screened` on success. On screening failure the candidate row still
exists with state `applied` and the failure is retryable from HR.

### Candidates

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/candidates/{id}` | Full detail, including a signed audio URL |
| `POST` | `/candidates/{id}/approve` | Mint interview token, set state `approved`, return the link |
| `POST` | `/candidates/{id}/reject` | Set state `rejected` |
| `POST` | `/candidates/{id}/rescreen` | Retry a failed screening |

### Interview

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/interview/{token}` | Session state. Drives which stage the candidate screen renders |
| `POST` | `/interview/{token}/start` | Generate the plan, create turn 1, return question 1 |
| `POST` | `/interview/{token}/answer` | Multipart `audio`. Transcribe, save turn, update state, return next question or completion |
| `GET` | `/interview/{token}/result` | HR-side. Full result with turns |

`GET /interview/{token}` response:

```json
{
  "status": "in_progress",
  "job_title": "Senior Python Developer",
  "total_questions": 8,
  "current_slot": 3,
  "current_question": "You mentioned a recommendation system..."
}
```

Returning `current_question` here is what makes reload-resume work. A candidate
who refreshes mid-interview lands on the same question, not a restart.

`POST /interview/{token}/answer` response:

```json
{
  "status": "in_progress",
  "next_slot": 4,
  "next_question": "How did you evaluate that model offline?",
  "total_questions": 8
}
```

or, on the final turn:

```json
{ "status": "complete" }
```

Evaluation runs synchronously inside that final call. It takes 10 to 25
seconds and the candidate screen shows `Reviewing your interview` throughout.

---

## 5. LLM stages

Five calls. Every one uses `response_schema` with a Pydantic model. No free-text
parsing anywhere.

Prompts live in `app/services/prompts.py` as module-level constants, never inline.

### 5.1 Rubric generation

Input: title, description, skills, experience.

```python
class Criterion(BaseModel):
    id: str            # stable slug, e.g. "python_django"
    name: str
    description: str
    points: int

class Rubric(BaseModel):
    criteria: list[Criterion]
    interview_topics: list[str]
```

Rules enforced in Python after generation:
- 4 to 7 criteria
- `points` sum to exactly 100
- `id` values unique and slug-shaped

On failure, retry once with the violation stated in the prompt. On second
failure, return a retryable error. Never repair the sum silently: a rubric
that was adjusted behind the scenes no longer matches what the model reasoned
about.

### 5.2 Screening

Input: the rubric, the introduction transcript, the extracted resume text, and
the declared skills list.

**Two sources, one score.** The resume carries structured facts the spoken
introduction usually will not: employers, dates, titles, tenure. The
introduction carries reasoning, ownership and communication quality a resume
cannot. Both are scored against the same rubric in a single call, and every
piece of evidence records which source it came from.

```python
class Evidence(BaseModel):
    source: Literal["introduction", "resume"]
    quote: str          # verbatim span from that source, not a paraphrase

class SubScore(BaseModel):
    criterion_id: str
    evidence: list[Evidence]   # declared before the points, deliberately
    points_awarded: int
    points_possible: int

class Screening(BaseModel):
    sub_scores: list[SubScore]
    total_score: int
    matched_skills: list[str]
    unevidenced_skills: list[str]
    resume_intro_conflicts: list[str]
    assessment: str
    recommendation: Literal["shortlist", "review", "reject"]
```

**Field order is load-bearing here too.** `evidence` is declared before
`points_awarded` so the model has to locate real supporting quotes before it
commits to a number. Declaring points first lets it pick a score and then go
looking for justification, which is the mechanism behind the 15 to 20 point
drift in CLAUDE.md.

Validated in Python:
- every `criterion_id` exists in the rubric
- every criterion appears exactly once
- `points_awarded` between 0 and `points_possible`
- `points_possible` matches the rubric
- `sum(points_awarded) == total_score`
- every `quote` appears in the source it names, after whitespace
  normalisation. A quote attributed to the resume that only exists in the
  transcript is a validation failure, not a near miss
- `evidence` may be empty only when `points_awarded` is 0

Quote matching is case and whitespace insensitive, because transcription and
PDF extraction both introduce line breaks a model will not reproduce byte for
byte. A quote elided with an ellipsis is split on the ellipsis and every
fragment must appear verbatim, which keeps grounding intact while avoiding a
wasted retry on a habit every model has. Measured 2026-08-14: without this,
every single screening call burned its retry budget on well founded evidence.

`resume_intro_conflicts` records where the two sources disagree, for example a
resume listing three years at an employer while the introduction says five.
Surfaced to HR as neutral observations, never as an accusation and never as a
score penalty. The system reports the discrepancy; the human decides what it
means.

If no resume was supplied, the call runs unchanged with an empty resume block
and every `Evidence.source` is `introduction`.

A sum mismatch is a validation failure, not a rounding detail. Retry once with
the arithmetic error stated. This is the rule that holds scores steady across
reruns.

`unevidenced_skills` is deliberately not `missing_skills`. The system knows
what the introduction did not evidence, not what the candidate cannot do, and
the field name should not let anyone forget that.

### 5.3 Interview plan

Runs once, at `POST /interview/{token}/start`.

Input: the rubric, the screening result, the introduction transcript.

```python
class PlannedQuestion(BaseModel):
    slot: int
    intent: str                 # what this question is for
    criterion_ids: list[str]
    depth: Literal["opening", "probing", "deep"]

class InterviewPlan(BaseModel):
    total_questions: int        # 5 to 10
    questions: list[PlannedQuestion]
```

Rules:
- Slots 1 to 3 are fixed intents: background, projects, personal contribution.
  These are planned, not generated, and their `depth` is `opening`
- Every rubric criterion appears in at least one slot
- `depth` progresses: no `deep` slot before slot 4
- `total_questions` scales with rubric breadth: 4 criteria gives 6 questions,
  7 criteria gives 9

The plan is stored and never regenerated. Only question wording is dynamic.

### 5.4 Turn result

One call per answered turn. It does three jobs in a fixed order: score the
answer that just arrived, extract what was learned from it, then generate the
next question.

Input: the answer transcript, the plan entry for the slot just answered, the
plan entry for the next slot, the interview state object, the relevant rubric
criteria.

```python
class AnswerScore(BaseModel):
    criterion_id: str
    points_awarded: int
    points_possible: int
    evidence: str          # a direct quote from the answer, not a paraphrase

class TurnResult(BaseModel):
    # Scoring first. The model must judge the answer before deciding
    # what to ask next, so a weak answer produces a probing follow-up
    # and a strong one moves on.
    answer_scores: list[AnswerScore]
    topics_identified: list[str]
    claims_made: list[str]

    # Then, and only then, the next question.
    next_question: str
    targets_criterion_ids: list[str]
    anchored_on_claim: str | None
```

**Field order is load-bearing. Do not reorder.** Structured output is generated
in declaration order, so scoring fields before question fields means the model
has assessed the answer by the time it writes the follow-up. Reversing them
produces questions written before the answer was understood.

`evidence` must be a span quoted from the answer. A paraphrase means the model
is inventing support for a score it already decided on. Validate that the
evidence string appears in the transcript after whitespace normalisation, and
retry once if it does not.

Scoring incrementally, one answer at a time, rather than all at the end:

- final evaluation drops from 10 to 25 seconds down to roughly 5, because it
  aggregates rather than reads the whole transcript
- each score is anchored to the single answer that produced it, which holds
  steadier than one pass judging eight answers at once
- it costs no extra API call, because the turn call was happening anyway

Prompt instruction shape, following the "say what to do" rule:

> Ask one question that probes {criterion names}. If the candidate has made a
> claim listed in `claims_made` that relates to this criterion, anchor the
> question to that specific claim and ask for a concrete detail about it. Ask
> about something in `criteria_remaining`. Phrase it as a single direct
> question under 30 words.

Validated in Python:
- the question is not substantially similar to any prior question, checked by
  normalised token overlap above a threshold in `app/core/heuristics.py`
- `targets_criterion_ids` are all real criterion ids

On a repeat, regenerate once with the prior questions listed and an explicit
instruction to ask about a different criterion.

### 5.5 Evaluation

Runs on the final answer submission. Because every answer was already scored in
§5.4, this call aggregates rather than re-reads. It receives the accumulated
per-answer scores and the transcript, and writes the narrative.

```python
class Evaluation(BaseModel):
    technical_score: int
    communication_score: int
    experience_score: int
    overall_score: int
    strengths: list[str]
    concerns: list[str]
    recommendation: Literal["shortlist", "review", "reject"]
```

The three sub-scores are computed in Python from the accumulated `AnswerScore`
rows, grouped by which rubric criteria map to each dimension. The model does
not invent them; it receives them and writes `strengths`, `concerns` and
`recommendation` against them.

Validated:
- all scores 0 to 100
- `overall_score` within 2 points of the weighted average
  (technical 0.5, communication 0.25, experience 0.25). Outside that, retry
- 2 to 4 strengths, 1 to 4 concerns, each a complete sentence referencing
  something the candidate actually said

### 5.6 Prompt builders

Prompts are functions returning a `(system, user)` tuple, not bare string
constants:

```python
def screening_prompts(rubric: Rubric, transcript: str,
                      declared_skills: list[str]) -> tuple[str, str]: ...
```

The builder composes state into a compact block so each call is self-contained
and independently testable. A prompt you cannot call with fixture inputs is a
prompt you cannot test.

---

## 6. Interview state object

Stored on `interviews.state_object`, rewritten after every answer.

```json
{
  "questions_asked": [
    { "slot": 1, "criterion_ids": ["relevant_experience"],
      "question": "Tell me about yourself..." }
  ],
  "answers": [
    { "slot": 1, "transcript": "I have been working...",
      "response_time_seconds": 9 }
  ],
  "topics_discussed": ["backend engineering", "recommender systems"],
  "claims_made": [
    "Built a recommendation system using collaborative filtering",
    "Five years of Python experience"
  ],
  "criteria_covered": ["relevant_experience"],
  "criteria_remaining": ["python_django", "sql_modelling",
                         "system_design", "communication"],
  "depth_by_topic": { "recommender systems": 1 }
}
```

`topics_discussed` and `claims_made` are extracted by the same Gemini call that
generates the next question, returned as part of a wrapper model, so answer
analysis costs no extra request. Keep the extraction fields out of
`NextQuestion` itself and put both inside a single `TurnResult` response model.

Cap `claims_made` at 12 entries, most recent first. An unbounded state object
grows the prompt every turn until latency becomes visible.

---

## 7. Ingestion

### 7.1 Resume extraction

```python
def extract_resume(pdf: bytes) -> str:
    """Text from a PDF resume. pypdf, pure Python, no external service."""
```

- **PDF only** in the MVP. Reject `.doc` and `.docx` with a clear message
  asking for a PDF. Adding `docx` later is a small change; adding it now adds
  a dependency and a format branch for a case that rarely appears
- Maximum 5MB. Above that returns `resume_too_large`
- Extracted text is normalised: collapse runs of whitespace, strip page
  furniture, cap at 20,000 characters
- **Image-only PDFs produce no text.** If extraction yields fewer than 200
  characters, return `resume_not_readable` with the message
  `This resume appears to be a scanned image. Upload a PDF with selectable
  text.` Do not fall back to OCR; that is a paid service or a heavy local
  dependency, and the candidate can fix it in ten seconds
- The raw file is stored in the `resumes` bucket regardless, so HR can always
  open the original

`pypdf` is MIT, pure Python and has no system dependencies. Do not add
`pydparser`, spaCy, or any resume-parsing library. Rubric does not need parsed
fields; the screening call reads the text directly against the rubric, which is
both simpler and better than keyword extraction.

### 7.2 Speech to text

```python
def transcribe(audio: bytes, filename: str) -> str:
    """Groq primary, faster-whisper fallback, in that order."""
```

**Groq path.** `whisper-large-v3-turbo`. Typically under 2 seconds for a
2-minute clip.

**Fallback triggers:** HTTP 429, HTTP 5xx, timeout above 15 seconds, or any
connection error. Never fall back on a 4xx that indicates a bad file; that is
a real error and should surface.

**Local path.** `faster-whisper`, `base`, `compute_type="int8"`, CPU. Roughly
20 to 40 seconds for a 2-minute clip. Load the model once at process start,
not per request.

**Formats.** Chrome sends `audio/webm;codecs=opus`, Safari sends `audio/mp4`.
Both are accepted by Groq directly. Pass the correct filename extension through
so the API infers the container. `faster-whisper` needs `ffmpeg` present.

**Limits.** Reject uploads above 20MB with a clear error. A 2-minute opus clip
is well under 2MB, so anything near the limit is a client bug.

---

## 8. DEMO_MODE

`DEMO_MODE=1` replays recorded responses instead of calling any external
service.

```
tests/cassettes/
  golden/
    rubric.json          rubric generation for the golden job
    screening.json       screening for the golden candidate
    plan.json            interview plan
    turn_02.json ...     one per generated question
    evaluation.json
    transcripts.json     audio hash to transcript
    rows.json            Supabase rows for the golden job and candidate
```

Matching: Gemini calls key on stage name plus a hash of the prompt inputs.
Transcription keys on a hash of the audio bytes. A miss in `DEMO_MODE` raises
loudly rather than falling through to a live call.

Record with `python -m tests.record_cassettes` against a real run of the golden
job end to end.

`rows.json` matters because Supabase makes the internet a hard dependency. With
it, the whole demo runs from a laptop on aeroplane wifi.

Build this before the first client demo, not after the first failure.

---

## 9. Errors

One error shape everywhere:

```json
{
  "error": {
    "code": "rubric_generation_failed",
    "message": "The model provider did not respond in time.",
    "retryable": true
  }
}
```

`message` is user-facing prose and goes straight into the UI. It never contains
a stack trace, a provider name, a status code or a model id.

| Code | HTTP | Retryable |
|---|---|---|
| `rubric_generation_failed` | 502 | yes |
| `screening_failed` | 502 | yes |
| `transcription_failed` | 502 | yes |
| `evaluation_failed` | 502 | yes |
| `schema_validation_failed` | 502 | yes |
| `audio_too_large` | 413 | no |
| `resume_too_large` | 413 | no |
| `resume_not_readable` | 400 | no |
| `resume_wrong_format` | 400 | no |
| `audio_unreadable` | 400 | no |
| `invalid_token` | 404 | no |
| `interview_already_complete` | 409 | no |
| `job_not_active` | 409 | no |
| `rate_limited` | 429 | yes |

Log the real exception server-side with the request id. Return the prose.

---

## 10. Layout

```
backend/
  app/
    main.py            app factory, CORS, router mounting
    config.py          settings from env, model ids, all thresholds
    heuristics.py      named constants only, no magic numbers elsewhere
    models.py          Pydantic response schemas for every LLM stage
    prompts.py         prompt constants
    llm.py             Gemini client, structured calls, retry logic
    stt.py             Groq primary, faster-whisper fallback
    resume.py          PDF text extraction and normalisation
    storage.py         Supabase client, buckets, signed URLs
    validation.py      post-generation checks for every stage
    interview.py       plan generation, state object, turn advancement
    scoring.py         band computation, weighted overall
    errors.py          error codes and the exception to response mapping
    cassettes.py       DEMO_MODE record and replay
    api/
      jobs.py
      apply.py
      candidates.py
      interview.py
  tests/
    cassettes/
    fixtures/
    test_validation.py
    test_interview_state.py
    test_scoring.py
    test_api.py
    record_cassettes.py
  .env.example
  pyproject.toml
```

`app/core/heuristics.py` holds every threshold as a named constant: band boundaries,
question-similarity threshold, criteria count bounds, claim cap, audio size
limit, timeouts. No numeric literal with meaning appears anywhere else.

---

## 11. Tests

Never assert on model prose. Assert structural invariants.

| Test | Asserts |
|---|---|
| `test_rubric_points_sum` | Criteria points total exactly 100 |
| `test_subscores_sum` | Screening sub-scores sum to the reported total |
| `test_criteria_ids_exist` | Every referenced criterion id is in the rubric |
| `test_plan_covers_rubric` | Every criterion appears in at least one planned slot |
| `test_no_repeat_questions` | No generated question exceeds the similarity threshold against any prior question |
| `test_state_object_grows_correctly` | After N answers, `criteria_covered` and `criteria_remaining` partition the criteria set |
| `test_band_boundaries` | Scores at 44, 45, 69, 70 land in the expected bands |
| `test_stt_falls_back_on_429` | Groq 429 routes to `faster-whisper`, 400 does not |
| `test_evidence_source_matches` | A quote attributed to the resume is not found only in the transcript |
| `test_image_pdf_rejected` | A scanned PDF returns `resume_not_readable`, not an empty string |

**Consistency harness.** Score one fixture transcript five times and assert the
range stays under the threshold in `app/core/heuristics.py`. There is no ground truth
here, so variance is the only measurable property. This is the test that proves
the sub-score discipline works, and the one that predicts whether a live rerun
during a demo will embarrass anyone.

**Synthetic candidate harness.** The only way to test an adaptive interviewer
without human subjects. A scripted model plays a candidate with a fixed
persona and plays through a full interview. A second call then grades the
**interviewer**, not the candidate:

| Check | Passes when |
|---|---|
| `no_repeats` | No question re-asks something already answered |
| `coverage` | Every rubric criterion was probed at least once |
| `anchoring` | Follow-ups reference specifics the candidate actually said |
| `progression` | Later questions go deeper, not wider |
| `no_leaking` | Questions do not hand the candidate the expected answer |

Run against two personas: one strong, one weak and vague. The weak persona is
the important one, because a vague answer is what makes a reactive interviewer
loop or drift.

This costs real API calls, so it runs on demand rather than in CI. Run it after
any change to the plan or turn prompts.

Adapted from the interviewer-grading approach in `IliaLarchenko/Interviewer`.
See `docs/prior-art.md`.

---

## 12. Build order

Matches the screen order in `docs/screens.md` where it can.

| Order | Work |
|---|---|
| 1 | Supabase project, schema, storage buckets, `.env.example`, FastAPI skeleton, health route |
| 2 | `stt.py` with both paths and the fallback test, `resume.py` extraction |
| 3 | `llm.py`, `models.py`, `prompts.py`, rubric generation, `POST /jobs` |
| 4 | Screening, `POST /apply`, consistency harness |
| 5 | Interview plan, state object, turn advancement, the three interview routes |
| 6 | Evaluation and result routes |
| 7 | Candidate list, approve and reject, token minting |
| 8 | `DEMO_MODE` cassettes recorded end to end |
| 9 | README, including un-pausing Supabase as step zero |

Item 8 is not optional and does not move later.

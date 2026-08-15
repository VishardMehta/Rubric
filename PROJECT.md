# Rubric - project brief

Client project. Status as of 2026-08-13.

## Documents

| Document | Contents |
|---|---|
| `CLAUDE.md` | Hard constraints and engineering rules. Loads automatically |
| `DESIGN.md` | Design tokens. Source of truth for values |
| `docs/design-system.md` | How tokens are applied. Components, states, rules |
| `docs/product.md` | Product structure, entity states, routes, the interview plan |
| `docs/screens.md` | Nine screen specifications |
| `docs/backend.md` | Schema, API, LLM stages, validation, tests |
| `docs/implementation-plan.md` | Sequential build plan. Start here |
| `docs/prior-art.md` | Open-source projects reviewed, what was adopted, attribution |

Implementation reads these as the source of truth. No screen or endpoint should
need to be reinterpreted from the client's original documents.

## Commercial terms

- Fee: Rs 3,500, fixed. Decided.
- Zero running cost. Free tiers only, including during development.
- Localhost only. No deployment, no domain.
- Client supplies their own API keys.
- Deliverable is an academic demo. Not for screening real candidates. This line
  belongs in the SOW. Automated scoring of people touches the DPDP Act, and in
  the US the Illinois AI Video Interview Act and NYC Local Law 144. Irrelevant
  for a localhost demo with fake candidates, which is exactly why it costs
  nothing to write down.

## Scope

The MVP flow, entity states and route map are in `docs/product.md` §3 to §5.
Out-of-scope modules are listed in §7 of that document: proctoring, anti-cheat,
GitHub and LinkedIn verification, PDF reports, email delivery.

### Scope change: HR accounts, requested after the MVP shipped

HR authentication and multi-user were fenced out of the original estimate and
appear as out-of-scope in `docs/product.md` §7, `README.md` and the fee basis
below. The client asked for them afterwards, so they were built and §7 was
updated to match. This is a real addition to the agreed scope, not a
clarification of it, and the fixed fee below was set without it. Flagged here
so the difference is on the record rather than absorbed silently.

Added with it: job ownership, so each account sees only its own roles and
applicants. Not added, and still out of scope for the same reason as before:
email delivery, and therefore password reset and HR invitations.

Nine screens: one landing, five HR, three candidate. Specified in
`docs/screens.md`.

## Stack

| Need | Choice |
|---|---|
| LLM | Gemini Flash free tier, `google-genai`, structured output |
| Speech to text | Groq `whisper-large-v3-turbo`, free tier |
| STT fallback | `faster-whisper` base, local, CPU |
| Text to speech | `window.speechSynthesis`, browser native |
| Audio capture | Native `MediaRecorder` |
| DB and storage | Supabase free tier, `service_role` from backend only |
| Backend | FastAPI, Pydantic v2 |
| Frontend | React, Vite, plain CSS with the token layer from `DESIGN.md` |
| Type | Inter, self-hosted, weights 400 / 500 / 600 |

## Timeline

Roughly 15 to 17 working days.

| Work | Days |
|---|---|
| Supabase project, schema, storage, FastAPI skeleton, STT with fallback | 1.5 |
| Resume extraction, rubric generation, screening, validation, consistency harness | 3 |
| Interview plan, state object, turn advancement, evaluation | 2 |
| Token layer, primitives, both shells | 1.5 |
| Interview screen, `VoiceRecorder`, `AudioLevelMeter` | 2 |
| Application screen with resume upload | 1.5 |
| Create Job and Jobs Dashboard | 1 |
| Job Detail and Candidate Detail | 1.5 |
| Interview Result | 1 |
| Landing and Interview Complete | 0.5 |
| DEMO_MODE cassettes, end-to-end testing, README | 1.5 |

This is higher than the 8 to 9 days estimated earlier in planning. Four
reasons, all of them real: the design system is authored from scratch rather
than adapted, the screen count went from five to nine, a landing page was
added, and resume upload was added alongside the voice introduction. The
estimate moved because the scope did.

## Build order

Backend order is in `docs/backend.md` §12. Frontend order is in
`docs/screens.md`, bottom section.

Both start with the interview. It is the hardest surface, the most novel, and
it defines the two components worth building carefully. Everything after it is
conventional work against patterns already established.

## Open questions for the client

1. **Does the AI speak the questions, or are they shown as text only?**
   Specified as spoken with text always visible, since `speechSynthesis` is
   free and adds no latency. If the client prefers text-only, the interview
   screen loses the TTS trigger and the auto-record starts on render instead.
   One line of behavior either way, but confirm it.

2. **Question count.** Specified as 5 to 10, set by the plan from rubric
   breadth. A 9-question interview runs roughly 12 to 15 minutes, which is long
   to demo live. Recommend demoing a 5-criterion job so the plan produces 6
   questions.

3. **Is n8n required in the architecture?** Currently not used. Orchestration
   runs in the backend: faster to build, easier to debug and hand over. n8n
   would add a visual workflow canvas that presents well in a report. Client's
   call, and it changes the estimate.

## Demo checklist

Run before any client demo. The first four are the ones that have actually
gone wrong.

**The day before**

- [ ] Supabase project un-paused. Free projects pause after about seven days
      idle and a paused project looks exactly like a broken application
- [ ] Cassettes current: re-record if any prompt changed since they were made.
      `cd backend && .venv/bin/python -m tests.record_cassettes`
- [ ] Offline replay proven:
      `.venv/bin/python -m pytest tests/test_demo_mode.py -q`
      This blocks IP networking inside the process and replays the whole flow
      from `tests/cassettes/`. If it passes, a laptop in aeroplane mode with
      no API keys can still run the demo
- [ ] Both suites green: `pytest -q` in `backend/`, `npm run build` in
      `frontend/`

**On the machine, an hour before**

- [ ] Backend on the port the frontend expects:
      `DEMO_MODE=1 .venv/bin/uvicorn app.main:app --port 8123`
- [ ] Log line `DEMO_MODE: using the in-memory store, not Supabase` present.
      Without it you are live against the providers and one 429 from ending
      the demo
- [ ] `DEMO_AUTH=1` if you want to sign in without remembering a password.
      The sign in screen says so on the page when it is on, and the backend
      logs it on boot. Turn it off before anything that is not a demo
- [ ] Register the demo HR account. `DEMO_MODE` starts from an in-memory
      store that resets on every restart, so the account has to be created
      again after each one. It claims the seeded job on registration, so a
      dashboard that looks empty means you skipped this
- [ ] `http://localhost:5273/jobs` shows the golden job with its candidate
- [ ] Microphone permission already granted in the demo browser profile, so
      the first question does not open a permission prompt
- [ ] Speech synthesis audible: system volume up, output device correct

**Know before you are asked**

- [ ] Re-running the same candidate gives the same score. That is the point of
      the sub-score discipline, and the consistency harness measures it:
      `.venv/bin/python -m tests.consistency_harness`
- [ ] The interview adapts. Show the transcript on Interview Result: each turn
      names the rubric criteria it probed, and the follow-ups quote the
      candidate
- [ ] Candidates never see a score, at any point, including on completion

**Known limits, say them before the client finds them**

- [ ] Registration is open and there is no password reset. Both need email
      delivery, which is out of scope. Say it before someone clicks around
      looking for "forgot password"
- [ ] The session token lives in `localStorage`, not an httpOnly cookie. Fine
      for localhost, would not be for a deployed build
- [ ] In `DEMO_MODE` a *new* recording cannot be transcribed: only the golden
      audio is in the cassettes. Live-recording a fresh answer needs
      `DEMO_MODE` off, which means live API calls and a rate-limit risk
- [ ] Rubric regeneration does not rescore candidates already screened

## Source documents

Client-supplied, kept for reference. The specifications in `docs/` supersede
them wherever they differ.

- `AI_Hiring_System_Roadmap.docx` - original roadmap. AI-generated, 32-week
  capstone scope, internally inconsistent in places. Every line is something
  the client may point at, so anything not in `docs/product.md` §7 is fenced
  out deliberately.
- `Executive Summary.pdf` - market and open-source research. Independently
  estimated 10 to 13 days for a narrower version of this MVP. Three of its
  recommendations are deliberately not followed: local `openai-whisper` is too
  slow on CPU, `pydparser` is redundant because rubric generation already
  extracts skills, and the React audio-recorder packages are unnecessary
  against native `MediaRecorder`.

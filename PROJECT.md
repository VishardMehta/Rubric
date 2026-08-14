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
GitHub and LinkedIn verification, PDF reports, email delivery, HR auth.

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

Run before any client demo.

- [ ] Supabase project un-paused
- [ ] `DEMO_MODE=1` verified working with the network disconnected
- [ ] Golden job and candidate present
- [ ] Microphone permission already granted in the demo browser profile
- [ ] Demo on a 5-criterion job so the interview is 6 questions

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

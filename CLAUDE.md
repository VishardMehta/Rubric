# Rubric

AI hiring system. Voice-first screening and interviewing, MVP scope.

## Core rule
The rubric is the contract. Stage 1 turns a job description into a scoring
rubric with explicit point allocations. Every downstream score is computed
against that rubric and nothing else. No holistic judgement, no vibes score.

## Scoring discipline
The model never emits a bare total. It emits per-criterion sub-scores that
sum to the total, and the sum is verified in Python before the row is saved.
A mismatch is a validation failure, not a rounding detail.

Reason: the same transcript scored twice will drift 15-20 points if you ask
for a single number. Sub-scores anchored to named rubric criteria hold
steady. The client will re-run the same candidate during a demo.

## Hard constraints
- Free tier only. No paid API calls at any point, including during
  development. If a feature needs a paid API, the feature is out of scope.
- Gemini SDK is `google-genai`. NOT `google-generativeai` (deprecated).
- Speech to text is Groq `whisper-large-v3-turbo` (free tier), with
  `faster-whisper` base model as the offline fallback.
- Do NOT use `openai-whisper` locally. It pulls ~2GB of torch and takes
  2-6 minutes to transcribe a 2-minute clip on a CPU laptop. It will kill
  the demo.
- Text to speech is the browser's `window.speechSynthesis`. No TTS API.
  It is free, needs no key, and has zero network latency, so the interview
  feels faster than the paid version.
- Audio capture is the native `MediaRecorder` API. No recorder packages.
  Chrome emits webm, Safari emits mp4. Handle both explicitly.
- No LangChain, LangGraph, Instructor, Celery, Redis, SQLAlchemy.
  Do not add dependencies without asking.
- Localhost only. No deployment, no domain, no hosted n8n.
- No em dashes in any output, comments, or docs. Use hyphens.

## Supabase
- Backend uses the `service_role` key and bypasses RLS. The frontend never
  talks to Supabase directly. One place to reason about access.
- `service_role` is a god key. Backend `.env` only. Never the frontend,
  never committed.
- `.env.example` holds variable names with empty values. Never a real value,
  not even temporarily. Real values live in `.env`, which is gitignored.
- Free projects pause after ~7 days idle and need a manual restore from the
  dashboard. Un-pausing is line 1 of the README and step 0 before any demo.

## DEMO_MODE is not optional
Free tiers rate-limit. A 429 during a client demo is unrecoverable in the
moment. Record real Gemini and Groq responses for one golden candidate, and
have `DEMO_MODE=1` replay from those cassettes instead of calling out.
Cache the Supabase rows for that candidate too, since Supabase makes the
internet a hard dependency.

Build this before the first client demo, not after the first failure.

## Interview context is the product
Follow-up questions come from a state object carried across every turn:
questions already asked, answers given, rubric criteria covered, criteria
still uncovered, depth reached per topic. It is passed into every
question-generation call with instructions to target what is still uncovered.

Without it you get repeated questions and generic follow-ups. With it you get
"how did you handle the cold-start problem" after a candidate mentions
collaborative filtering. That difference is the whole product.

## Prompt authoring: say Y, never write "never X" alone
A bare prohibition in a system prompt is weaker than telling the model what to
say instead. Give it the vocabulary you want, not just the vocabulary you are
banning. Applies especially to the screening reasoning and the interview
follow-up instructions.

## Testing
Never assert on exact LLM prose. Assert structural invariants only: sub-scores
sum to the total, every cited criterion exists in the rubric, no question
repeats a prior question's topic.

Scoring consistency needs its own harness: same transcript, five runs, assert
score variance stays under threshold. There is no ground truth here, so
variance is the only thing you can actually measure.

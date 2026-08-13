# Rubric product structure

What the product is, who uses it, what states things move through, and where
the boundaries are.

---

## 1. What Rubric is

Rubric turns a job description into a scoring rubric, then screens and
interviews candidates against that rubric by voice.

The name is the architecture. Stage one produces a rubric with explicit point
allocations. Every score after that is computed against those criteria and
nothing else. There is no holistic judgement anywhere in the system.

**One sentence for the landing page:** Rubric reads your job description,
builds a scoring rubric, and screens every applicant against it by voice.

---

## 2. Two experiences

### HR

A hiring dashboard used repeatedly by someone who is comfortable with it.
Dense, fast, scannable. Sidebar shell.

What HR can do:
- Create a job and see the rubric Rubric generated from it
- See every applicant ranked by screening score
- Open a candidate and see the score broken down by rubric criterion, the
  voice introduction transcript, matched and missing skills, and the reasoning
- Approve a candidate for interview, which generates an interview link
- Copy that link and send it themselves
- Review a completed interview: overall and sub-scores, strengths, concerns,
  full transcript, recommendation

### Candidate

A single-use, high-stakes, distraction-free flow. Centered shell, no
navigation.

What a candidate does:
- Opens an application link, enters name and email, records a voice
  introduction
- Later, opens an interview link and completes a voice interview of 5 to 10
  adaptive questions
- Sees a confirmation and nothing else

**The candidate never sees a score.** Not their screening score, not their
interview score, not a band, not a recommendation. This is a product decision,
not an oversight.

---

## 3. Full flow

```
HR creates a job
      │
      ▼
Rubric analyses the job description
      │  produces criteria with point allocations summing to 100
      ▼
HR shares the application link
      │
      ▼
Candidate records a voice introduction
      │
      ▼
Introduction is transcribed
      │
      ▼
Candidate is screened against the rubric
      │  per-criterion sub-scores, matched and missing skills, reasoning,
      │  recommendation
      ▼
HR reviews the ranked list
      │
      ▼
HR approves a candidate            HR rejects a candidate
      │                                    │
      ▼                                    ▼
Interview token generated              flow ends
      │
      ▼
HR copies and sends the interview link
      │
      ▼
Candidate opens the link
      │
      ▼
Interview plan is generated
      │  maps rubric criteria to planned questions, sets total question count
      ▼
┌──── Question is asked ────────────────────┐
│           │                               │
│           ▼                               │
│     Candidate answers by voice            │
│           │                               │
│           ▼                               │
│     Answer is transcribed                 │
│           │                               │
│           ▼                               │
│     Interview state is updated            │
│     topics, claims, criteria covered      │
│           │                               │
│           ▼                               │
│     Next question is generated,           │
│     targeting uncovered criteria          │
│           │                               │
└───────────┘  repeats 5 to 10 times        │
            │                               │
            ▼                               │
      Interview marked complete ────────────┘
            │
            ▼
Interview is evaluated against the rubric
            │  overall and sub-scores, strengths, concerns, recommendation
            ▼
HR reviews the result
```

---

## 4. Entities and states

### Job

| State | Meaning |
|---|---|
| `analyzing` | Created, rubric generation in progress |
| `active` | Rubric ready, accepting applications |
| `closed` | No longer accepting applications |

A job with `analyzing` state shows a loading state on its detail page and
cannot be shared yet.

### Candidate

| State | Set by | Meaning |
|---|---|---|
| `applied` | Application submitted | Audio saved, transcription in progress |
| `screening` | Transcription complete | Being scored against the rubric |
| `screened` | Screening complete | Score and recommendation available, awaiting HR |
| `approved` | HR action | Interview token minted, link ready |
| `rejected` | HR action | Terminal |
| `interviewing` | Candidate opened interview link | Interview in progress |
| `interviewed` | Final answer submitted | Evaluation in progress or complete |

State is a single field on the candidate row. The UI derives everything it
shows from it. Never infer state by checking whether some other field is null.

### Interview

An interview exists once a candidate is `approved`. Its own sub-state:

| State | Meaning |
|---|---|
| `not_started` | Token minted, link never opened |
| `in_progress` | At least one question asked |
| `complete` | All planned questions answered |
| `evaluated` | Evaluation written |

---

## 5. Routes

### HR

| Path | Screen |
|---|---|
| `/` | Landing |
| `/jobs` | Jobs Dashboard |
| `/jobs/new` | Create Job |
| `/jobs/:jobId` | Job Detail and candidate ranking |
| `/jobs/:jobId/candidates/:candidateId` | Candidate Detail |
| `/jobs/:jobId/candidates/:candidateId/interview` | Interview Result |

### Candidate

| Path | Screen |
|---|---|
| `/apply/:jobId` | Application and voice introduction |
| `/apply/:jobId/done` | Application submitted |
| `/interview/:token` | Interview |
| `/interview/:token/done` | Interview complete |

Candidate routes are unauthenticated and identified only by job id or token.
Interview tokens are opaque, single-candidate, and not guessable.

There is no HR authentication in the MVP. This is a localhost demo. Note it in
the README so it is a stated decision rather than an oversight.

---

## 6. The interview plan

The single most important backend concept, and the thing that separates Rubric
from a wrapper around a chat model.

When a candidate opens their interview link, before the first question, Rubric
generates a plan:

- Total question count, 5 to 10, chosen from rubric breadth
- An opening sequence of 2 to 3 fixed-intent questions: background, projects,
  personal contribution
- A mapping from each remaining planned slot to the rubric criteria it should
  probe
- A difficulty progression, so later questions go deeper rather than wider

The plan is stored and does not change. What adapts is the **wording** of each
question, generated at the moment it is asked, from the interview state.

This hybrid matters. Purely reactive questioning follows whatever the candidate
mentioned first and can spend an entire interview on one topic, leaving most of
the rubric unprobed. The plan guarantees coverage; the state guarantees
relevance.

### Interview state object

Carried into every question generation call:

```
questions_asked      list of {slot, criterion_ids, question_text}
answers              list of {slot, transcript, response_time_seconds}
topics_discussed     list of topic strings extracted from answers
claims_made          list of candidate claims worth probing or verifying
criteria_covered     rubric criterion ids already probed
criteria_remaining   rubric criterion ids not yet probed
depth_by_topic       map of topic to how many turns have gone into it
```

The generation instruction targets `criteria_remaining` first, and uses
`claims_made` to make the question specific.

Worked example. Candidate says they built a recommendation system with
collaborative filtering. `claims_made` gains that claim, `topics_discussed`
gains "recommender systems". The next question targets an uncovered criterion,
say system design, using the claim as its anchor:

> How did you handle the cold-start problem in that recommender?

Not:

> Tell me about your experience with system design.

---

## 7. Scope

### In the MVP

Everything in §3. Nine screens, listed in `docs/screens.md`.

### Out of the MVP

Documented as future modules, not built:

| Module | Note |
|---|---|
| Webcam proctoring | Face detection, multiple-face, no-face, tab switching, screenshots |
| Anti-cheat and integrity scoring | Response-time analysis, AI-authorship signals |
| GitHub and LinkedIn verification | Separate optional module. LinkedIn has no free API and blocks scraping, so any real version is GitHub-only and should be described that way |
| PDF report generation | |
| Email delivery | HR copies the link and sends it themselves |
| HR authentication and multi-user | |
| Candidate re-application and retakes | |
| Rubric editing by HR | Rubric is generated and read-only. Regenerate is the only affordance |

### Deliberate non-goals

- No dark mode
- No deployment. Localhost only
- No paid API calls at any point
- No claim of verified concurrency beyond 5 to 10 simultaneous candidates

---

## 8. Language rules

The interface has a voice. It is precise and never anthropomorphic.

| Do not write | Write |
|---|---|
| AI is thinking | Scoring against rubric |
| Our AI recommends | Scored 72 against the rubric |
| The AI believes the candidate | The transcript matched 9 of 11 criteria |
| Magic, smart, powerful | Nothing. Delete the sentence |
| Candidate failed | Scored below the shortlist threshold |
| Best candidate | Highest scoring candidate |

The system reports what it measured. It does not have opinions about people.

Candidate-facing copy is warmer than HR-facing copy but follows the same rule.
It reassures without promising: `Your interview is complete and has been sent
for review.` Not: `Great job! You did really well.`

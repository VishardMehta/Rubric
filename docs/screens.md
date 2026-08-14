# Rubric screen specifications

Nine screens. One landing, five HR, three candidate.

Each spec gives purpose, layout, components, every state, and interactions.
Token names refer to `DESIGN.md`. Behavior rules refer to `docs/design-system.md`.

ASCII layouts show hierarchy and order, not pixel positions.

---

## 0. Landing

**Route** `/` · **Shell** none, own layout · **Max width** 1080

Purpose: explain Rubric in one screen and send HR into the product. This is the
only screen where marketing language is appropriate.

```
                            Rubric                    [ Open dashboard ]
  ─────────────────────────────────────────────────────────────────────────


          Every candidate, scored against the same rubric.


          Rubric reads your job description, builds a scoring
          rubric, and screens every resume and voice introduction
          against it.


                        [ Open dashboard ]


  ─────────────────────────────────────────────────────────────────────────


     01  Describe the role              02  Candidates apply
         Rubric extracts the                A resume plus a two
         criteria and assigns               minute spoken
         point allocations.                 introduction.

     03  Everyone is scored the same    04  Interview the shortlist
         Per-criterion sub-scores           Five to ten adaptive
         against one rubric, not a          questions that follow what
         holistic opinion.                  the candidate actually said.


  ─────────────────────────────────────────────────────────────────────────
                      Rubric · localhost demo
```

**Components** `Button` primary, `Section`

**Notes**
- Headline `display`, subhead `body-lg` at `ink-secondary`, max 60ch
- The four steps are a 2x2 grid at wide, single column under 768. Numbers in
  `label` style at `ink-tertiary`. No icons, no cards, no borders
- Vertical rhythm 96px between regions
- One accent element on the screen: the primary button, repeated twice
- No screenshots, no testimonials, no pricing, no feature grid

---

## 1. Jobs Dashboard

**Route** `/jobs` · **Shell** HR

Purpose: see every job and its pipeline at a glance, and post a new one.

```
  Jobs                                                     [ Post a job ]
  ─────────────────────────────────────────────────────────────────────────

  Senior Python Developer                                          Active
  48 applicants · 12 shortlisted · 7 interviewed          Posted 4 Aug
  ─────────────────────────────────────────────────────────────────────────
  Frontend Engineer                                                Active
  23 applicants · 6 shortlisted · 2 interviewed           Posted 9 Aug
  ─────────────────────────────────────────────────────────────────────────
  Data Analyst                                                  Analyzing
  Building rubric from description                       Posted 13 Aug
  ─────────────────────────────────────────────────────────────────────────
```

**Components** `PageHeader`, `DataTable` in list mode, `StatusChip`

**Interactions**
- Whole row is the click target, goes to `/jobs/:jobId`
- A job in `analyzing` state is not clickable and shows its progress line in
  `caption` `ink-secondary`
- Sort by posted date descending. No sort controls in the MVP

**Empty state**

```
No jobs yet

Post a job and Rubric will build a scoring rubric from
the description, then screen every applicant against it.

[ Post a job ]
```

**Responsive** Under 768, counts wrap to a second line and the status chip
moves under the title.

---

## 2. Create Job

**Route** `/jobs/new` · **Shell** HR · **Content max width** 640

Purpose: capture the job, then show the rubric that was generated from it. The
rubric reveal is the moment the product explains itself, so it happens here and
is not hidden behind a later click.

### Stage A, form

```
  Jobs / New job
  Post a job
  ─────────────────────────────────────────────────────────────────────────

  Job title
  ┌───────────────────────────────────────────────────────────────────────┐
  │ Senior Python Developer                                               │
  └───────────────────────────────────────────────────────────────────────┘
  The role as it will appear to candidates.

  Job description
  ┌───────────────────────────────────────────────────────────────────────┐
  │                                                                       │
  │                                                                       │
  └───────────────────────────────────────────────────────────────────────┘
  Rubric reads this to build the scoring criteria. More detail produces a
  better rubric.

  Required skills
  ┌───────────────────────────────────────────────────────────────────────┐
  │ [Python ×] [Django ×] [PostgreSQL ×]  Type a skill and press Enter    │
  └───────────────────────────────────────────────────────────────────────┘

  Experience required
  ┌───────────────────────────────────────────────────┐
  │ 2 to 4 years                                    ▾ │
  └───────────────────────────────────────────────────┘

                                                     [ Build rubric ]
```

**Components** `TextField`, `TextArea`, `TagInput`, `Select`, `Button`

**Validation** on blur. Title required. Description required, minimum 120
characters with the message `Add more detail so Rubric can build meaningful
criteria.` At least one skill required.

### Stage B, generating

The form is replaced, not overlaid:

```
  Analyzing job description

  Extracting criteria and assigning point allocations.
```

Single state, no fake sub-steps. Typically 3 to 8 seconds.

### Stage C, rubric

```
  Jobs / Senior Python Developer
  Rubric ready
  ─────────────────────────────────────────────────────────────────────────

  Every applicant will be scored against these criteria.

  ┌───────────────────────────────────────────────────────────────────────┐
  │  Python and Django                                            25 pts  │
  │  Production experience with Python web frameworks, ORM use,           │
  │  and testing practice.                                                │
  │  ───────────────────────────────────────────────────────────────────  │
  │  SQL and data modelling                                       20 pts  │
  │  Schema design, query performance, and working with relational        │
  │  data at scale.                                                       │
  │  ───────────────────────────────────────────────────────────────────  │
  │  System design                                                20 pts  │
  │  ...                                                                  │
  │  ───────────────────────────────────────────────────────────────────  │
  │  Communication                                                20 pts  │
  │  ───────────────────────────────────────────────────────────────────  │
  │  Relevant experience                                          15 pts  │
  │  ───────────────────────────────────────────────────────────────────  │
  │  Total                                                       100 pts  │
  └───────────────────────────────────────────────────────────────────────┘

  Application link
  ┌─────────────────────────────────────────────────────────┐
  │ localhost:5273/apply/a3f2c1              [ Copy ]       │
  └─────────────────────────────────────────────────────────┘

  [ Regenerate rubric ]                        [ Go to job ]
```

**Components** `RubricPanel`, `CopyLinkField`, `Button`

**Notes**
- Criterion name `body-strong`, points `score-inline` right-aligned,
  description `body` `ink-secondary` at 68ch
- Points are neutral ink, not semantic. They are allocations, not scores
- Total row separated by hairline, `body-strong`
- Rubric is read-only in the MVP. `Regenerate rubric` is a secondary button and
  warns if applicants already exist
- `Copy` shows a toast: `Application link copied`

**Error state** Generation failure is recoverable and keeps the form data:

```
Rubric could not be generated

The model provider did not respond in time. Your job
description is saved.

[ Try again ]
```

---

## 3. Job Detail and candidate ranking

**Route** `/jobs/:jobId` · **Shell** HR

Purpose: the working screen. Every applicant, ranked, with enough information
to decide who to open.

```
  Jobs / Senior Python Developer
  Senior Python Developer                            [ Copy application link ]
  ─────────────────────────────────────────────────────────────────────────

  48 applicants      12 shortlisted      7 interviewed      Posted 4 Aug

  ▸ Rubric · 5 criteria · 100 points

  ─────────────────────────────────────────────────────────────────────────
  All 48    Shortlist 12    Review 21    Reject 15
  ─────────────────────────────────────────────────────────────────────────

   #   Candidate                Score   Skills      Recommendation   Status
  ─────────────────────────────────────────────────────────────────────────
   1   Priya Nair                  84   9 of 11     Shortlist        Interviewed
       priya@example.com
  ─────────────────────────────────────────────────────────────────────────
   2   Arun Menon                  71   8 of 11     Shortlist        Approved
       arun@example.com
  ─────────────────────────────────────────────────────────────────────────
   3   Kavya Rao                   58   6 of 11     Review           Applied
       kavya@example.com
  ─────────────────────────────────────────────────────────────────────────
```

**Components** `PageHeader`, `StatRow`, `RubricPanel` collapsed, `DataTable`,
`ScoreInline`, `RecommendationChip`, `StatusChip`, `CopyLinkField`

**Interactions**
- Rubric row is a disclosure, collapsed by default. Expanding shows the full
  panel from screen 2
- Filter tabs filter by recommendation band. Counts are live
- Sorted by score descending. Rank column reflects that order and is not a
  stored value
- Row click opens Candidate Detail
- A candidate still in `applied` or `screening` shows an em-space in the score
  column and `Screening` as status, not a zero

**Notes**
- Exactly one tinted element per row, the recommendation chip. The score is
  colored text on plain background
- Stat row is text on canvas, not four boxes

**Empty state**

```
No applications yet

Share the application link and candidates can apply
with a voice introduction.

[ Copy application link ]
```

**Responsive** Under 768, rows become stacked cards: name and score on the
first line, email second, chips third.

---

## 4. Candidate Detail

**Route** `/jobs/:jobId/candidates/:candidateId` · **Shell** HR

Purpose: everything known about one applicant before the interview decision.
Split layout, scores left, evidence right.

```
  Jobs / Senior Python Developer / Priya Nair
  Priya Nair                                    [ Reject ]  [ Approve for interview ]
  priya@example.com · Applied 6 Aug
  ─────────────────────────────────────────────────────────────────────────

  ┌─────────────────────────────┐  ┌──────────────────────────────────────┐
  │  SCREENING SCORE            │  │  Voice introduction                  │
  │                             │  │                                      │
  │  84                         │  │  ▶ ────────────────  1:52            │
  │  out of 100 · Shortlist     │  │                                      │
  │                             │  │  ▸ Transcript                        │
  │  ─────────────────────────  │  │                                      │
  │                             │  └──────────────────────────────────────┘
  │  Python and Django          │
  │              22 / 25  ████  │  ┌──────────────────────────────────────┐
  │  SQL and data modelling     │  │  Skills                              │
  │              14 / 20  ███   │  │                                      │
  │  System design              │  │  Matched                             │
  │               9 / 20  ██    │  │  [Python] [Django] [PostgreSQL]      │
  │  Communication              │  │  [REST] [Docker]                     │
  │              15 / 20  ███   │  │                                      │
  │  Relevant experience        │  │  Not evidenced                       │
  │              12 / 15  ████  │  │  [Kubernetes] [Kafka]                │
  │  ─────────────────────────  │  │                                      │
  │  Total       72 / 100       │  └──────────────────────────────────────┘
  └─────────────────────────────┘
                                   ┌──────────────────────────────────────┐
                                   │  Assessment                          │
                                   │                                      │
                                   │  The introduction evidenced five     │
                                   │  years of Python work with clear     │
                                   │  Django and PostgreSQL detail...     │
                                   └──────────────────────────────────────┘
```

**Components** `PageHeader`, `Split` at 5:7, `ScoreHero`, `ScoreBreakdown`,
`EvidenceList`, `AudioPlayer`, `TranscriptView`, `Chip`, `Card`, `Button`,
`Modal`

**Interactions**
- `Approve for interview` mints the token, moves state to `approved`, and
  replaces the action bar with a `CopyLinkField` plus a toast
- `Reject` opens a confirmation modal. Wording: `Reject Priya Nair? They will
  not receive an interview link. This cannot be undone in the MVP.`
- Transcript is a disclosure, collapsed by default
- `Not evidenced` is the label for missing skills, not `Missing`. The
  distinction is real: the system knows what neither source mentioned, not what
  the candidate cannot do
- **Every evidence quote is tagged with its source.** Expanding a criterion in
  the breakdown shows the quotes that earned the points, each labelled
  `Introduction` or `Resume` in `label` style at `ink-tertiary`. This is how HR
  sees that a score came from a written claim rather than a spoken explanation
- **Conflicts appear as a neutral panel**, only when non-empty:

```
  ┌──────────────────────────────────────┐
  │  Differences between sources         │
  │                                      │
  │  · Resume lists 3 years at Zoho.     │
  │    The introduction said 5 years.    │
  └──────────────────────────────────────┘
```

  `surface-sunken` background, `ink` text, no semantic color and no warning
  icon. The system reports the discrepancy. It does not accuse anyone, and the
  discrepancy carries no score penalty

**Post-approval state**

```
  Priya Nair                                                      Approved
  ─────────────────────────────────────────────────────────────────────────

  Interview link
  ┌─────────────────────────────────────────────────────────┐
  │ localhost:5273/interview/9f3c...              [ Copy ]  │
  └─────────────────────────────────────────────────────────┘
  Send this link to the candidate. It works once and expires when
  the interview is complete.
```

**Interviewed state** adds a link to Interview Result at the top of the left
column:

```
  Interview complete · Overall 78          [ View interview result → ]
```

**Loading** While `screening`, the left column shows
`Scoring against rubric` and the right column shows the transcript once
available. Do not block the whole screen.

---

## 5. Interview Result

**Route** `/jobs/:jobId/candidates/:candidateId/interview` · **Shell** HR

Purpose: the outcome of the voice interview. This is the screen that carries
the demo.

```
  Jobs / Senior Python Developer / Priya Nair / Interview
  Interview result                                    [ Back to candidate ]
  Priya Nair · 8 questions · 14 min · Completed 11 Aug
  ─────────────────────────────────────────────────────────────────────────

  OVERALL

  78
  out of 100 · Shortlist

  ─────────────────────────────────────────────────────────────────────────

  Technical            Communication          Experience
  74                   85                     76
  out of 100           out of 100             out of 100

  ─────────────────────────────────────────────────────────────────────────

  ┌────────────────────────────────┐  ┌────────────────────────────────────┐
  │  Strengths                     │  │  Concerns                          │
  │                                │  │                                    │
  │  · Explained the cold-start    │  │  · Could not describe how the      │
  │    handling in their           │  │    recommender was evaluated       │
  │    recommender with specifics  │  │    offline                         │
  │  · Gave concrete numbers on    │  │  · System design answers stayed    │
  │    dataset size and latency    │  │    at a high level                 │
  └────────────────────────────────┘  └────────────────────────────────────┘

  ─────────────────────────────────────────────────────────────────────────

  Transcript

  01  Tell me about yourself and the work you have done recently.
      SQL and data modelling · Relevant experience              answered in 9s

      I have been working as a backend engineer for about five years...
      ▶ ──────────────  1:12

  ─────────────────────────────────────────────────────────────────────────

  02  You mentioned a recommendation system using collaborative
      filtering. How did you handle the cold-start problem?
      System design                                            answered in 6s

      For new users we fell back to a popularity model weighted by...
      ▶ ──────────────  0:48
```

**Components** `ScoreHero`, three `ScoreInline` blocks, `Card`, `TranscriptView`,
`AudioPlayer`

**Notes**
- One hero score. The three sub-scores are `score-large`, evenly spaced, not
  in cards, not colored unless they cross a band boundary
- Each transcript turn shows which rubric criteria that question probed, in
  `label` style at `ink-tertiary`. This is the visible proof that questions
  were planned rather than random
- Response time is shown in `caption`, right-aligned. It is context, not a
  score, and carries no color
- Answer text at 68ch. Audio playback per answer, collapsed player
- Strengths and concerns are plain bulleted lists. Concerns are not red

**Loading** While evaluation runs:

```
Reviewing the interview

Scoring eight answers against the rubric.
```

**Not-yet state** If reached before completion, redirect to Candidate Detail.

---

## 6. Application and voice introduction

**Route** `/apply/:jobId` · **Shell** Candidate

Purpose: a stranger's first contact with the product. Must be obvious and
calm.

```
                              Rubric


                    Senior Python Developer
                    Applying with a voice introduction


  ─────────────────────────────────────────────────────────────────────────

   Your name
   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘

   Email
   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘

  ─────────────────────────────────────────────────────────────────────────

   Resume
   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   │              Drop your resume here, or choose a file                │
   │                        PDF only, up to 5 MB                         │
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘

  ─────────────────────────────────────────────────────────────────────────

   Voice introduction

   Tell us who you are, what you have worked on, and what you built.
   About two minutes is plenty. Your resume covers where you worked;
   this covers how you think.

              ┌───────────────────────────────────────┐
              │                                       │
              │              ●  Record                │
              │                                       │
              └───────────────────────────────────────┘

              Your browser will ask for microphone access.

                                                  [ Submit application ]
```

**Components** `CandidateShell`, `TextField`, `FileDropzone`, `VoiceRecorder`,
`AudioLevelMeter`, `Button`

### Resume upload states

**Idle** Dashed `hairline-strong` border, radius `xl`, 120px tall, centered
label at `ink-secondary`. Not a card, not filled.

**Selected**

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │  priya-nair-resume.pdf   248 KB                          [ Remove ] │
   └─────────────────────────────────────────────────────────────────────┘
```

Solid border, filename in `mono`, size in `caption`. No preview thumbnail.

**Rejected** Border becomes `negative`, message replaces the caption:

| Case | Message |
|---|---|
| Not a PDF | `Rubric reads PDF resumes. Export yours as a PDF and try again.` |
| Over 5 MB | `That file is over 5 MB. Try exporting it again at a smaller size.` |
| Image-only PDF | `This resume appears to be a scanned image. Upload a PDF with selectable text.` |

The image-only case is caught server-side, after upload, because it needs
extraction to detect. Return the candidate to the form with the file cleared
and the message shown.

### Recorder states

**Idle** Large record control, `accent` circle glyph, `body-strong` label.

**Permission pending** Control disabled, caption becomes
`Waiting for microphone access`.

**Permission denied** Replaces the recorder with the recovery block from
design-system §17.

**Recording**

```
              ┌───────────────────────────────────────┐
              │   ● 0:47    ▁▃▅▇▅▃▁▂▄▆▄▂▁            │
              │                                       │
              │            [ Stop recording ]         │
              └───────────────────────────────────────┘
```

- Live dot in `live`, pulsing at 1s, disabled under reduced motion
- Timer `mono`, tabular
- Level meter driven by real input. If input is silent for 3 seconds, caption
  becomes `We are not picking up any sound` in `caution`

**Recorded**

```
              ┌───────────────────────────────────────┐
              │   ▶ ────────────────────  1:52        │
              │                                       │
              │   [ Record again ]                    │
              └───────────────────────────────────────┘
```

**Submitting** Button shows a spinner, keeps width. States progress:
`Uploading` then `Reading your resume` then `Transcribing your introduction`.

**Validation** Submit is disabled until name, email, a resume and a recording
all exist. A
recording under 20 seconds warns rather than blocks:
`That is quite short. Longer introductions score more reliably.`

**Responsive** Single column at every width. Recorder is full width under 640.

---

## 7. Interview

**Route** `/interview/:token` · **Shell** none, own full-viewport layout

The most important screen in the product. It answers three questions
continuously: am I being heard, how far through am I, what happens next.

No sidebar, no wordmark, no navigation, no footer. Nothing is clickable except
the single control.

### Stage 1, ready

```



                        Senior Python Developer

                        Voice interview

                        Eight questions. You will hear and read each
                        one, then answer out loud. There is no time
                        limit and no way to go back.

                        Find somewhere quiet. Your microphone stays
                        on for the whole interview.


                              [ Start interview ]



```

### Stage 2, question

```



                             Question 3 of 8
                        ────────────────────────


              You mentioned a recommendation system using
              collaborative filtering. How did you handle
              the cold-start problem?



                          ● ▁▃▅▇▅▃▁▂▄▆▄▂▁  0:24


                            [ Done answering ]



```

**Layout**
- Vertically centered in the viewport, max width 640
- `Question 3 of 8` in `label` style at `ink-secondary`
- Under it a 240px progress track, 3px, `hairline` with `accent` fill at
  3 of 8. Quiet, not a stepper with circles
- Question in `display`, `ink`, max 24 words per line target, centered
- Level meter and timer 48px below the question
- Single control 48px tall, `accent` primary, 64px below the meter

**Behavior**
- Recording starts automatically when the question finishes rendering, or when
  TTS finishes speaking if TTS is enabled. The candidate is never asked to
  press record
- Question text stays visible while TTS speaks it. Text is never replaced by
  audio
- Silence for 5 seconds after speech began shows `Still listening` in
  `caption`, not an error
- No countdown timer. Elapsed time only. A countdown creates panic and there is
  no time limit

### Stage 3, processing

The control is replaced in place, same height, no layout shift:

```
                        Transcribing your answer
```

then

```
                        Preparing the next question
```

Each label changes only when the backend actually reaches that stage. The
question text from the previous turn stays on screen, dimmed to
`ink-tertiary`, until the next question replaces it. This keeps the screen from
going blank during the gap.

Announced to assistive technology via `aria-live="polite"`.

### Stage 4, transition

New question fades in over 320ms with an 8px rise. Progress track animates to
its new width over the same duration. Under reduced motion, both are instant.

### Error states

**Answer could not be transcribed**

```
                  We could not hear that answer clearly.

                       [ Record that answer again ]
```

Same slot, same layout. The candidate is never blamed and never loses the
interview.

**Connection lost mid-interview**

```
                        Connection interrupted

              Your answers so far are saved. Reconnecting.
```

Auto-retries. On repeated failure, offers `Reload and continue`. Because
answers are persisted per turn, reload resumes at the correct question.

**Invalid or expired token** Full-region error from design-system §17.

### Responsive

At 375px: question drops to `title-1`, max width becomes viewport minus 40px,
control becomes full width, meter narrows. Everything else is unchanged. The
screen was designed for this width first.

---

## 8. Interview complete

**Route** `/interview/:token/done` · **Shell** Candidate

Purpose: end cleanly and say nothing more.

```



                              Rubric


                    Your interview is complete.


              Your answers have been sent for review. The
              hiring team will be in touch.

              You can close this window.



```

**Notes**
- No score, no band, no feedback, no summary of what they said
- No call to action, no link, no button. There is nothing left to do
- Reopening the interview link after completion lands here, not on an error

---

## Screen build order

Build in this order. Each stage produces something demonstrable.

| Order | Screen | Why here |
|---|---|---|
| 1 | Interview (7) | Hardest, most novel, defines the component library's difficult parts |
| 2 | Application (6) | Shares `VoiceRecorder` and `AudioLevelMeter` with the interview |
| 3 | Create Job (2) | Unblocks everything downstream, shows the rubric |
| 4 | Job Detail (3) | The main HR working surface |
| 5 | Candidate Detail (4) | Establishes `ScoreHero` and `ScoreBreakdown` |
| 6 | Interview Result (5) | Reuses score components, adds transcript |
| 7 | Jobs Dashboard (1) | Simplest HR screen, needs nothing new |
| 8 | Interview complete (8) | Trivial |
| 9 | Landing (0) | Last. It is the easiest to build and the easiest to cut |

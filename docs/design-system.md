# Rubric design system

Token values live in `DESIGN.md`. This document defines how they are applied.
Every rule here is written against a real Rubric surface. If a rule cannot name
the screen it governs, it does not belong in this file.

---

## 1. Principles

Rubric is an instrument for making a judgment about a person. That single fact
drives every decision below.

**Calm over energetic.** Someone is deciding another person's future. The
interface must not feel like a game or a growth dashboard. No confetti, no
gradients, no motivational copy.

**The number is the content.** Scores, criteria and transcripts are the
product. Chrome exists to frame them and then get out of the way.

**Show the reasoning, not just the verdict.** A score with no visible basis is
untrustworthy. Every score in Rubric can be expanded to the rubric criteria
that produced it.

**Two users, two moods.** HR is confident and scanning. The candidate is
nervous and one-shot. These need different interfaces, not one interface with
a different header.

**Never fake certainty.** The system does not know if someone is a good hire.
It knows how an answer scored against a stated rubric. Language throughout must
reflect that difference.

---

## 2. Two shells

### HR shell

```
┌────────────┬──────────────────────────────────────────────┐
│            │  Page title                    [Primary CTA] │
│  Rubric    │  ───────────────────────────────────────────  │
│            │                                              │
│  Jobs      │  Content, max-width 1280                     │
│            │                                              │
│            │                                              │
│            │                                              │
└────────────┴──────────────────────────────────────────────┘
   240px
```

Sidebar is `surface` on a `canvas` page. One hairline separates them. No
shadow. Navigation items are the only persistent chrome.

### Candidate shell

```
┌────────────────────────────────────────────────────────────┐
│                          Rubric                            │
│                                                            │
│                                                            │
│                  Content, max-width 640                    │
│                     centered, vertical                     │
│                                                            │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

No sidebar, no navigation, no back button, no footer links. A quiet wordmark at
top and nothing else. The candidate cannot navigate because there is nowhere
else to go.

The interview screen removes even the wordmark. See §16.

---

## 3. Color in practice

Three roles, never mixed.

| Role | Tokens | Where it appears in Rubric |
|---|---|---|
| Neutral | `canvas`, `surface`, `ink*`, `hairline*` | Ninety percent of every screen |
| Accent | `accent*` | Primary buttons, links, focus rings, active nav item, wordmark, the record button |
| Semantic | `positive`, `caution`, `negative` and tints | Score chips and score numbers only |

**The test:** if you remove all semantic color from a screen, it should still
be fully usable. Semantic color reinforces a label that is already there. It
never carries meaning alone.

Correct:

```
Screening score
72   Shortlist
```
with `72` in `positive` and a `positive-tint` chip behind `Shortlist`.

Wrong:

```
Screening score
[ solid green pill: 72 ]
```

### Score bands

| Band | Range | Token | Label |
|---|---|---|---|
| Strong | 70 to 100 | `positive` | Shortlist / Strong |
| Borderline | 45 to 69 | `caution` | Review |
| Weak | 0 to 44 | `negative` | Reject |

Bands are defined once, in the backend, and returned with the score. The
frontend never computes a band from a number. Thresholds change; hardcoded
frontend logic drifts from the backend and the two disagree in front of a
client.

---

## 4. Typography in practice

Nine text roles plus three number roles. Do not invent a tenth.

| Role | Used for |
|---|---|
| `display` | Landing hero, the interview question |
| `title-1` | Page titles: "Jobs", candidate name |
| `title-2` | Section headings: "Rubric", "Interview transcript" |
| `title-3` | Card and panel headings |
| `body-lg` | Landing subhead, candidate-facing instructions |
| `body` | Default everywhere |
| `body-strong` | Emphasised inline, table row primary cell |
| `caption` | Metadata, timestamps, helper text |
| `label` | Uppercase eyebrows above a value |
| `mono` | Interview tokens, IDs, file names |
| `score-hero` | The single dominant score on Candidate Detail and Interview Result |
| `score-large` | Sub-scores in a breakdown |
| `score-inline` | Scores inside table rows |

**Prose width.** Any paragraph longer than two lines gets `max-width: 68ch`.
This applies to AI reasoning, strengths, concerns and answer transcripts. Full
browser-width prose is the fastest way to make a premium layout look cheap.

**Never bold a whole row.** If everything is emphasised, nothing is.

---

## 5. Spacing and rhythm

Base unit 4px. The scale in `DESIGN.md` is the complete set of allowed values.

| Gap | Between |
|---|---|
| 4 to 8 | Icon and its label, score and its unit |
| 12 to 16 | Related controls, form field and its helper text |
| 20 to 24 | Padding inside a card or panel |
| 32 to 40 | Sibling sections on a page |
| 64 to 96 | Major page regions, landing sections |

Vertical rhythm on HR pages: 32px between sections. On candidate screens: 48px.
The candidate flow is deliberately slower and airier.

---

## 6. Layout and grid

Rubric does not need a formal 12-column grid. Three layout primitives cover
every screen.

**Stack.** Vertical flow with a single gap value. The default.

**Split.** Two columns at a fixed ratio, collapsing to a stack under 768px.
Used on Candidate Detail (scores left, evidence right) at 5:7.

**Table.** See §10.

Content max-widths are in `DESIGN.md`. Never let a table stretch past 1280px;
a 1900px-wide row is unreadable regardless of how much screen exists.

---

## 7. Cards and panels

A card groups things that are read together. It is not a decoration and not a
default container.

**Use a card for:** the rubric block, a sub-score breakdown, a single interview
turn, a strengths or concerns group.

**Do not use a card for:** a single statistic, a page section that already has
a heading, a table, a form.

Anatomy:

```
surface background
hairline border, 1px
radius md (10px)
padding 20px, or 24px if the card is the primary content
no shadow
```

Cards get a shadow only when they float above the page, which in Rubric means
never. Popovers and modals float. Cards do not.

**Statistics are not cards.** On Job Detail, the counts row is text on canvas
with generous spacing:

```
48 applicants     12 shortlisted     7 interviewed
```

not four bordered boxes.

---

## 8. Buttons

Three levels. One primary per screen region.

| Level | Fill | Border | Text | Height |
|---|---|---|---|---|
| Primary | `accent` | none | `on-accent` | 40px |
| Secondary | `surface` | `hairline-strong` | `ink` | 40px |
| Tertiary | none | none | `accent` | 36px |
| Destructive | `surface` | `hairline-strong` | `negative` | 40px |

Radius `sm`. Horizontal padding 16px, 20px for primary. Font `body-strong`.

States: hover shifts fill one step (`accent-hover`) or background to
`surface-hover`. Pressed shifts one more step and applies no transform.
Disabled drops to `ink-disabled` text on `surface-sunken` with no border
change. Loading replaces the label with a spinner and the button keeps its
width so the layout does not jump.

**Destructive actions are never filled.** Reject on Candidate Detail is a
bordered button with `negative` text, not a red block. Red fill on a button
that rejects a human being is the wrong tone for this product.

**Verbs, always.**

Good: `Post job`, `Approve for interview`, `Copy interview link`,
`Start interview`, `Done answering`.

Bad: `Submit`, `Confirm`, `OK`, `Continue`.

---

## 9. Inputs

Every input has a visible label above it. Placeholder text is never the label.

```
Job title
┌──────────────────────────────────────────┐
│ Senior Python Developer                  │
└──────────────────────────────────────────┘
The role as it will appear to candidates.
```

- Label: `body-strong`, `ink`, 6px above the field
- Field: 40px tall, `surface`, `hairline-strong` border, radius `sm`, 12px
  horizontal padding, `body` text
- Helper: `caption`, `ink-secondary`, 6px below
- Focus: 2px `accent-ring` outline offset 2px, border becomes `hairline-focus`
- Error: border `negative`, message replaces helper text in `negative`

Textareas: same treatment, minimum 120px tall, resize vertical only. The job
description field starts at 200px.

**Skills input** is a tag field. Type, press Enter or comma, get a chip.
Chips are `surface-sunken` with `ink` text, radius `sm`, with a remove control.
Skill chips are neutral, not accent. They are data, not actions.

**Validation happens on blur, not on submit.** Telling someone at the end of a
form that field two was wrong is a design failure.

---

## 10. Tables

Rubric's ranked candidate list is the most important table in the product.

```
Rank  Candidate            Score   Skills        Recommendation   Status
────────────────────────────────────────────────────────────────────────────
 1    Priya Nair             84    9 of 11       Shortlist        Interviewed
      priya@example.com
 2    Arun Menon             71    8 of 11       Shortlist        Approved
      arun@example.com
 3    Kavya Rao              58    6 of 11       Review           Applied
      kavya@example.com
```

Rules:

- Header row: `label` style, `ink-secondary`, hairline underneath, sticky on
  scroll
- No vertical rules. No zebra striping. Horizontal hairlines between rows only
- Row height 64px when a row carries two lines, 48px for single-line rows
- Numbers right-aligned and tabular. Text left-aligned
- Row hover: `surface-hover`. The whole row is the click target
- Sort defaults to score descending. Column headers that sort show a chevron
  on hover, not permanently
- Secondary information (email) sits under the primary cell in `caption`
  `ink-secondary`, not in its own column

Under 768px the table becomes a stacked list of cards, one per candidate, with
the score prominent and other fields as label-value pairs.

---

## 11. Badges and status

Two distinct badge types. Do not merge them.

**Recommendation chip** carries semantic color, because it carries meaning.

```
positive-tint background, positive text  →  Shortlist
caution-tint background, caution text    →  Review
negative-tint background, negative text  →  Reject
```

Radius `sm`, padding 2px 8px, `caption` weight 500.

**Status chip** is always neutral, because a pipeline stage is not good or bad.

```
surface-sunken background, ink-secondary text
Applied · Screened · Approved · Interviewing · Interviewed
```

Same geometry, no color. A candidate at "Applied" is not failing at anything.

**No dots without labels.** A colored dot with no text fails for colorblind
users and communicates nothing to anyone else.

---

## 12. Score presentation

This is the section that most defines whether Rubric looks premium or looks
like a school project.

### Hero score

One per screen, maximum. Candidate Detail shows the screening score. Interview
Result shows the overall interview score.

```
SCREENING SCORE

72
out of 100 · Shortlist
```

- Number in `score-hero`, colored by band
- `label` eyebrow above in `ink-secondary`
- Denominator and band in `caption`, `ink-secondary`, with the band word in its
  semantic tone
- No progress ring, no gauge, no arc. A number set large is more confident than
  a number wrapped in a donut

### Breakdown

Every hero score expands into the rubric criteria that produced it. This is
Rubric's core promise made visible.

```
Python and Django          22 / 25   ████████████████████░░░░
SQL and data modelling     14 / 20   ██████████████░░░░░░░░░░
System design               9 / 20   █████████░░░░░░░░░░░░░░░
Communication              15 / 20   ███████████████░░░░░░░░░
Relevant experience        12 / 15   ████████████████████░░░░
                          ───────
                           72 / 100
```

- Criterion name in `body`, `ink`
- Score in `score-inline`, tabular, right-aligned before the bar
- Bar is 4px tall, radius pill, `hairline` track. Fill is `ink-secondary`, not
  semantic color. Five colored bars in a stack is noise; the numbers already
  carry the comparison
- The total row is separated by a hairline and set in `body-strong`

### In tables

Score is `score-inline`, colored by band, with no chip or background. The
recommendation chip in the adjacent column carries the tint. One tinted element
per row.

### Never

- Never show a score the backend did not compute
- Never animate a score counting up
- Never show a percentage sign; scores are out of 100 but they are points, not
  percentages
- Never place two hero scores on one screen

---

## 13. Navigation

**HR sidebar.** Wordmark at top, 24px padding. Nav items are 36px tall, radius
`sm`, `body` text. Active item: `accent-tint` background, `accent` text,
`body-strong` weight. Hover: `surface-hover`. The active state uses background
plus weight plus color, so it survives grayscale.

For the MVP there is exactly one nav item, Jobs. Do not build a nav shell with
five placeholder links.

**Breadcrumbs** appear on Job Detail and below. One level only:

```
Jobs / Senior Python Developer
```

`caption`, `ink-secondary`, with the parent as an `accent` link.

**Candidate flow has no navigation.** Progress is communicated by state, not
by a nav element the candidate could click.

---

## 14. Modals

Rubric uses modals in exactly two places: reject confirmation, and the
microphone permission explainer. Everything else is inline.

- `surface`, radius `lg`, `shadow-lg`, max-width 440px
- Scrim `overlay-scrim`
- Title `title-3`, body `body`, actions right-aligned with primary last
- Escape closes, focus traps inside, focus returns to the trigger on close
- Entrance: 200ms `ease-entrance`, opacity plus 8px rise. No scale bounce

A modal must be answering a question. If it is displaying information, it
should have been a panel.

---

## 15. Loading states

Rubric has four operations slow enough to need a state. Each shows what is
actually happening.

| Operation | Duration | State shown |
|---|---|---|
| Rubric generation | 3 to 8s | `Analyzing job description` |
| Application screening | 8 to 20s | `Transcribing introduction` then `Scoring against rubric` |
| Interview turn | 5 to 10s | `Transcribing your answer` then `Preparing the next question` |
| Interview evaluation | 10 to 25s | `Reviewing your interview` |

Rules:

- The label changes when the backend actually moves to the next stage. Never
  run a timer that advances labels on its own
- No percentage bars. Rubric cannot know a percentage, so showing one is a lie
- Skeletons only for content that will occupy the same shape, such as the
  candidate table. Never a skeleton for a score
- A spinner alone is only acceptable under 1 second

**Language.** The system is never a person.

Good: `Scoring against rubric`, `Transcribing your answer`.
Bad: `AI is thinking`, `Our AI is working its magic`, `Hang tight`.

---

## 16. Empty states

Three parts: what is missing, why it matters, what to do.

**Jobs Dashboard, no jobs**

```
No jobs yet

Post a job and Rubric will build a scoring rubric
from the description, then screen every applicant
against it.

[ Post a job ]
```

**Job Detail, no applicants**

```
No applications yet

Share the application link and candidates can
apply with a voice introduction.

[ Copy application link ]
```

**Candidate Detail, not yet interviewed**

Inline, not a full empty state:

```
Interview not started

This candidate was approved on 12 August. The
interview link has not been opened yet.

[ Copy interview link ]
```

Never render a blank region. Never render an empty table with headers and no
rows.

---

## 17. Error states

Three parts: what happened, why, what the user can do. Never a status code,
never a stack trace.

**Recoverable, inline**

```
Screening could not be completed

The model provider did not respond in time. The
candidate's introduction and transcript are saved.

[ Retry screening ]
```

**Blocking, full region**

```
This interview link is no longer valid

The link may have expired, or the interview may
already be complete.

If you believe this is a mistake, contact the
person who sent you this link.
```

**Candidate-facing errors are gentler and never blame the candidate.**

Good: `We could not hear that answer clearly. Try recording it again.`
Bad: `Invalid audio. Transcription failed.`

**Microphone permission denied** gets its own treatment with recovery steps,
because it is the single most likely failure in the candidate flow:

```
Rubric needs your microphone

The interview is answered by voice, so we need
microphone access to continue.

Click the microphone icon in your browser's
address bar and choose Allow, then reload.

[ Reload and try again ]
```

---

## 18. Motion

Motion explains a state change. It never announces itself.

| Change | Duration | Easing |
|---|---|---|
| Hover, focus, press | 120ms | standard |
| Panel expand, chip appear | 200ms | standard |
| Modal, screen transition | 200 to 320ms | entrance |
| Question transition in interview | 320ms | entrance |

Allowed: opacity, small translate (max 8px), background color, border color,
height on disclosure.

Never: scale bounce, spring overshoot, looping ambient animation, particles,
gradient movement, anything on the page background.

The audio level meter in the interview is the one continuously animating
element in the product, and it is driven by real microphone input. It is
instrumentation, not decoration.

Respect `prefers-reduced-motion: reduce` by dropping all transitions to 0.01ms
and replacing the question transition with an instant swap. The level meter
becomes a static filled bar showing current level without animation.

---

## 19. Accessibility

Minimum bar, non-negotiable:

- Semantic HTML. `button` for actions, `a` for navigation, `table` for tables,
  `main`, `nav`, `section`. No clickable `div`
- Every input has a `label` element, associated by `for` and `id`
- Focus is always visible: 2px `accent-ring`, 2px offset. Never `outline: none`
  without a stronger replacement
- Tab order follows visual order
- Color is never the only signal. Every score band has a word next to it
- Touch targets 44px minimum on compact widths
- The interview screen announces state changes via `aria-live="polite"` so a
  screen reader user hears "Transcribing your answer"
- Audio players have real controls, not a custom play button with no keyboard
  support
- Text scales to 200% without horizontal scroll

Contrast floors are in `DESIGN.md`. `ink-tertiary` is not for meaningful text.

---

## 20. Responsive behavior

| Width | HR | Candidate |
|---|---|---|
| Wide, 1180+ | Full sidebar, table view, split layouts | Centered 640, unchanged |
| Medium, 768 to 1179 | Sidebar collapses to 64px icons, tables keep all columns, splits become stacks | Centered 640, unchanged |
| Compact, under 768 | Sidebar becomes a top bar, tables become stacked cards | Full width minus 20px gutters |

The candidate flow is designed mobile-first and barely changes across widths,
because a candidate is realistically on a laptop or a phone and the layout is
a single column either way.

The interview screen must work at 375px. Question text drops from `display` to
`title-1`, the level meter narrows, the control stays 48px tall and full width.

---

## 21. Component inventory

Build these. Nothing else.

**Primitives**
`Button`, `IconButton`, `TextField`, `TextArea`, `Select`, `TagInput`,
`Checkbox`, `Chip`, `Divider`, `Spinner`

**Layout**
`HRShell`, `CandidateShell`, `PageHeader`, `Section`, `Card`, `Split`

**Data**
`DataTable`, `TableRow`, `StatRow`, `ScoreHero`, `ScoreBreakdown`,
`ScoreInline`, `RecommendationChip`, `StatusChip`

**Feedback**
`EmptyState`, `ErrorState`, `LoadingState`, `Toast`, `Modal`

**Domain**
`RubricPanel`, `VoiceRecorder`, `AudioLevelMeter`, `AudioPlayer`,
`TranscriptView`, `InterviewQuestion`, `InterviewProgress`, `CopyLinkField`

`VoiceRecorder` and `AudioLevelMeter` are the two components worth building
carefully. Everything else is conventional.

---

## 22. Anti-patterns

Do not ship any of these.

- A wall of saturated green and red badges in the candidate table
- A donut, gauge or radial progress ring around a score
- A score that animates counting up from zero
- Every section wrapped in a bordered card
- A statistic in its own box, four across
- Gradients of any kind, including subtle ones on buttons
- Glassmorphism, blur panels, translucent cards
- Neon or violet "AI" accents, glowing borders, sparkle icons
- The word "magic" anywhere in the interface
- `AI is thinking` or any anthropomorphised loading text
- Percentage-based progress bars for operations of unknown duration
- Fake stages that advance on a timer
- A chat bubble layout for the interview. It is an assessment, not a
  conversation with a chatbot
- Showing the candidate their score
- Emoji in scores, statuses or system messages
- A dark mode toggle
- Placeholder navigation items that lead nowhere
- Tooltips carrying information the user needs to complete a task

---

## 23. Screen review checklist

Before any screen is considered done:

- [ ] Purpose is clear within two seconds
- [ ] Exactly one primary action
- [ ] Exactly one hero score, or none
- [ ] All numbers tabular
- [ ] Prose constrained to 68ch
- [ ] Semantic color appears at most twice per viewport
- [ ] Screen is fully usable with all color removed
- [ ] Empty state written
- [ ] Error state written
- [ ] Loading state names real backend work
- [ ] Keyboard navigable end to end, focus always visible
- [ ] Works at 375px
- [ ] No fabricated data of any kind

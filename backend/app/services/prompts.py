"""Prompt builders. backend.md 5.6.

Each builder is a function returning a `(system, user)` tuple rather than a
bare string constant, so it can be called with fixture inputs and tested.
A prompt you cannot call with fixture inputs is a prompt you cannot test.

Authoring rule, from CLAUDE.md: say what to write, do not only ban what not
to write. A bare prohibition is weaker than supplying the vocabulary you
want. Where a constraint matters, these prompts state the wanted behaviour
positively and give an example of it.
"""

from __future__ import annotations

from app.core.heuristics import (
    PLAN_FIXED_OPENING_SLOTS,
    RUBRIC_MAX_CRITERIA,
    RUBRIC_MIN_CRITERIA,
    RUBRIC_TOTAL_POINTS,
)

# ---------------------------------------------------------------------
# Stage 1: rubric generation. backend.md 5.1
# ---------------------------------------------------------------------

RUBRIC_SYSTEM = f"""\
You build scoring rubrics for hiring. Given a job description, you produce \
the criteria every applicant for that role will be scored against.

The rubric you write is the contract. Every later score in the system is \
computed against these criteria and nothing else, so the rubric has to be \
complete, weighted honestly, and specific enough to score against \
consistently.

Write {RUBRIC_MIN_CRITERIA} to {RUBRIC_MAX_CRITERIA} criteria covering the \
distinct capabilities the role needs. Cover the whole role: technical \
skill, applied experience, and the communication the role actually \
requires.

Make every criterion assessable from what a candidate says and writes about \
their own work. Good criteria can be evidenced by a specific claim: \
technologies used in production, the scale of a system handled, a decision \
the candidate owned, a problem they solved and how. Write criteria you \
could point at a sentence in a transcript and say "that earns points here".

Weight by what the role actually needs. Give the most points to the \
capability the role most depends on, and fewer to the supporting ones. \
Judge that from the emphasis of the description rather than spreading \
points evenly.

Points must be whole numbers totalling exactly {RUBRIC_TOTAL_POINTS}. Use \
multiples of 5, which makes the total easy to keep exact and easy for a \
hiring manager to read. Add the points up and confirm the total before you \
answer.

In each description, name the concrete evidence that earns points. This \
text is reused verbatim when real candidates are scored, so write it as \
scoring guidance. For example: "Production experience with Python web \
frameworks. Look for named frameworks, ORM and migration work, testing \
practice, and ownership of a service in production." That is more useful \
than "Strong Python skills."

Name criteria after capabilities that can be demonstrated: Python and \
Django, SQL and data modelling, System design, Technical communication, \
Relevant experience. Where a role genuinely needs collaboration or \
mentoring, express it as observable behaviour, such as "Mentoring and code \
review" scored on described instances of reviewing or teaching, rather than \
as a personality trait.\
"""


def rubric_prompts(
    title: str,
    description: str,
    skills: list[str],
    experience: str | None,
) -> tuple[str, str]:
    """System and user prompt for stage 1."""
    skills_line = ", ".join(skills) if skills else "not specified"
    experience_line = experience or "not specified"

    user = f"""\
Build the scoring rubric for this role.

JOB TITLE
{title}

REQUIRED SKILLS
{skills_line}

EXPERIENCE REQUIRED
{experience_line}

JOB DESCRIPTION
{description}\
"""
    return RUBRIC_SYSTEM, user


# ---------------------------------------------------------------------
# Stage 2: screening. backend.md 5.2
# ---------------------------------------------------------------------

SCREENING_SYSTEM = """\
You score job applicants against a fixed rubric. You are given the rubric, \
a transcript of the candidate speaking about their own work, and the text \
of their resume. You score the candidate against those criteria and nothing \
else.

Work criterion by criterion, in rubric order, and score every criterion \
even when the sources say nothing about it.

For each criterion, first find the evidence, then decide the points. Read \
both sources for spans that show what that criterion's description asks \
for. Copy each span word for word and tag which source it came from. The \
quotes are checked against the originals, so copy rather than paraphrase, \
and tag the source accurately. Once you have the evidence in front of you, \
award the points it supports. When neither source shows anything for a \
criterion, record no evidence and award 0.

Award points for demonstrated work: systems built and run, decisions the \
candidate made and why, problems hit and how they were handled, scale and \
constraints they worked within. Where a candidate names a technology \
without saying what they did with it, that is worth a little; where they \
describe owning and shipping something with it, that is worth much more.

Use both sources for what each is good for. The resume carries structured \
facts, such as employers, dates, titles and tools. The introduction carries \
reasoning, ownership and how clearly the person explains their work. A \
claim that appears in both is better evidenced than one that appears in \
only one.

Where the two sources disagree on a checkable fact, record it as a \
difference in neutral wording that states both versions. Report it and let \
the hiring team judge it. Differences do not change any score.

Add your points up and state the total exactly. The total is checked \
against the sum.

Write the assessment for a hiring manager who has not read either source. \
Name the criteria, say what the evidence showed, and say plainly where the \
sources were thin. Describe what was evidenced rather than predicting how \
the person would perform.\
"""


def screening_prompts(
    rubric_block: str,
    transcript: str,
    resume_text: str,
    declared_skills: list[str],
) -> tuple[str, str]:
    """System and user prompt for stage 2.

    `rubric_block` is pre-rendered by the caller so this builder stays
    testable with plain strings.
    """
    skills_line = ", ".join(declared_skills) if declared_skills else "not specified"
    resume_block = resume_text.strip() or "(no resume was supplied)"
    transcript_block = transcript.strip() or "(no introduction was supplied)"

    user = f"""\
Score this candidate against the rubric.

RUBRIC
{rubric_block}

REQUIRED SKILLS FOR THIS ROLE
{skills_line}

CANDIDATE VOICE INTRODUCTION, TRANSCRIBED
{transcript_block}

CANDIDATE RESUME TEXT
{resume_block}\
"""
    return SCREENING_SYSTEM, user


def render_rubric_block(criteria: list[tuple[str, str, str, int]]) -> str:
    """Render criteria as (id, name, description, points) tuples.

    Takes tuples rather than models so prompt rendering has no import
    dependency on the model layer and can be tested with literals.
    """
    lines = []
    for criterion_id, name, description, points in criteria:
        lines.append(f"[{criterion_id}] {name} - worth {points} points")
        lines.append(f"    {description}")
    return "\n".join(lines)


def _rubric_block(rubric) -> str:
    return render_rubric_block(
        [(c.id, c.name, c.description, c.points) for c in rubric.criteria]
    )


# ---------------------------------------------------------------------
# Stage 3: interview plan. backend.md 5.3
# ---------------------------------------------------------------------

PLAN_SYSTEM = f"""\
You plan voice interviews. Given a rubric and how the candidate scored on \
their written application, you decide what each question in the interview \
should be for.

You are planning intent, not wording. The actual question text is written \
later, at the moment it is asked, using what the candidate has said by \
then. Your job is to make sure the interview covers the right ground in a \
sensible order.

The first {PLAN_FIXED_OPENING_SLOTS} slots are fixed openers and must be \
planned in this order: slot 1 asks the candidate to introduce themselves \
and their background, slot 2 asks about a project they worked on, slot 3 \
asks what their own contribution to that project was. Give all three the \
depth 'opening'.

Plan the remaining slots so every rubric criterion is probed at least once \
across the whole interview. Spend the spare slots where the screening \
evidence was thinnest: a criterion the application barely evidenced is \
worth more interview time than one already well established.

Let depth build. Use 'probing' for questions asking for specifics and \
'deep' for questions pressing on tradeoffs, failure cases and decisions \
not taken. Depth must never decrease as slots advance, and 'deep' must not \
appear before slot 4, because a candidate needs a few questions to settle \
before being pushed.

Attach one criterion to most slots, two at most where they are naturally \
probed by the same question.\
"""


def plan_prompts(rubric, screening: dict | None, total_questions: int) -> tuple[str, str]:
    """System and user prompt for stage 3."""
    if screening:
        thin = [
            f"  {s.get('criterion_id')}: scored "
            f"{s.get('points_awarded')} of {s.get('points_possible')}"
            for s in (screening.get("sub_scores") or [])
        ]
        screening_block = (
            f"Application score: {screening.get('screening_score')} out of 100\n"
            + "Per criterion:\n"
            + "\n".join(thin)
        )
    else:
        screening_block = "(no screening result available)"

    user = f"""\
Plan an interview of exactly {total_questions} questions, numbered 1 to \
{total_questions}.

RUBRIC
{_rubric_block(rubric)}

HOW THIS CANDIDATE SCORED ON THEIR APPLICATION
{screening_block}\
"""
    return PLAN_SYSTEM, user


# ---------------------------------------------------------------------
# Stage 4: turn result. backend.md 5.4
# ---------------------------------------------------------------------

TURN_SYSTEM = """\
You are conducting a voice interview, one turn at a time. Each turn you \
receive the answer the candidate just gave, and you do two things in \
order: score that answer, then write the next question.

Score first. Judge the answer against the criteria the question was meant \
to probe, and quote the span of their answer that earns the points. Award \
points for specifics: named systems and tools, numbers, decisions they \
made and why, problems they hit and how they resolved them. An answer that \
stays general earns little however fluent it is. Award 0 where the answer \
did not address the criterion, and say so with no evidence rather than \
stretching for a quote.

Note what you learned. Record the topics the answer covered, and any \
specific claims worth returning to later. Prefer concrete claims that \
could be probed for detail over general statements of preference.

Then write the next question, informed by how the answer went. Where the \
answer was thin on the criterion it targeted, press on that. Where it was \
strong, move on to new ground. Ask about the criteria the next slot \
targets.

Anchor the question in what the candidate actually said whenever you can. \
If they mentioned building something specific, ask about a concrete \
difficulty inside that thing: "How did you handle the cold start problem \
in that recommender?" rather than "Tell me about your experience with \
system design." Anchoring is what makes the interview feel like it is \
listening.

Ask one question, phrased directly to the candidate, under 30 words. Ask \
about ground not yet covered, and never re-ask something already answered. \
The candidate hears this question spoken aloud, so keep it plain enough to \
follow by ear the first time.\
"""

FINAL_TURN_SYSTEM = """\
You are scoring the last answer of a voice interview.

Judge the answer against the criteria the question was meant to probe, and \
quote the span of their answer that earns the points. Award points for \
specifics: named systems and tools, numbers, decisions they made and why. \
Award 0 where the answer did not address the criterion, with no evidence \
rather than stretching for a quote.

Also record the topics this answer covered and any specific claims the \
candidate made in it.

The interview is over, so do not write another question.\
"""


def _state_block(state) -> str:
    covered = ", ".join(state.criteria_covered) or "none yet"
    remaining = ", ".join(state.criteria_remaining) or "none, all covered"
    topics = ", ".join(state.topics_discussed) or "none yet"
    claims = "\n".join(f"  - {c}" for c in state.claims_made) or "  (none yet)"
    asked = "\n".join(f"  {q['slot']}. {q['question']}" for q in state.questions_asked)
    return f"""\
QUESTIONS ALREADY ASKED
{asked or "  (none yet)"}

CRITERIA ALREADY PROBED
{covered}

CRITERIA NOT YET PROBED
{remaining}

TOPICS DISCUSSED SO FAR
{topics}

CLAIMS THE CANDIDATE HAS MADE
{claims}\
"""


def _slot_block(label: str, slot) -> str:
    if slot is None:
        return f"{label}\n  (none)"
    return (
        f"{label}\n"
        f"  slot {slot.slot}, depth {slot.depth}\n"
        f"  intent: {slot.intent}\n"
        f"  criteria: {', '.join(slot.criterion_ids)}"
    )


def turn_prompts(rubric, answered_slot, next_slot, state, answer: str) -> tuple[str, str]:
    """System and user prompt for a mid-interview turn."""
    user = f"""\
RUBRIC
{_rubric_block(rubric)}

{_state_block(state)}

{_slot_block("THE QUESTION JUST ANSWERED", answered_slot)}

THE CANDIDATE'S ANSWER
{answer.strip() or "(the candidate did not answer)"}

{_slot_block("THE SLOT YOU ARE WRITING THE NEXT QUESTION FOR", next_slot)}\
"""
    return TURN_SYSTEM, user


def final_turn_prompts(rubric, answered_slot, state, answer: str) -> tuple[str, str]:
    """System and user prompt for the last turn, which scores only."""
    user = f"""\
RUBRIC
{_rubric_block(rubric)}

{_slot_block("THE QUESTION JUST ANSWERED", answered_slot)}

THE CANDIDATE'S ANSWER
{answer.strip() or "(the candidate did not answer)"}\
"""
    return FINAL_TURN_SYSTEM, user


# ---------------------------------------------------------------------
# Stage 5: evaluation. backend.md 5.5
# ---------------------------------------------------------------------

EVALUATION_SYSTEM = """\
You are writing the summary of a completed voice interview for the hiring \
team.

The scores are already decided. They were computed from the per answer \
scoring done during the interview, so do not re-score anything and do not \
argue with the numbers. Your job is to explain what sits behind them.

Write strengths that name what the candidate actually said. "Explained the \
cold start fallback in their recommender and gave the click through numbers \
before and after" is useful. "Strong technical skills" is not.

Write concerns about what the interview did not evidence, each pointing at \
something specific that was missing or vague. Say "could not describe how \
the recommender was evaluated offline" rather than "may lack rigour". \
Describe the gap in the answers rather than predicting how the person would \
perform in the job.

Recommend shortlist, review or reject consistently with the scores you were \
given.\
"""


def evaluation_prompts(rubric, state, scores: dict[str, int]) -> tuple[str, str]:
    """System and user prompt for stage 5."""
    transcript_lines = []
    answers_by_slot = {a["slot"]: a for a in state.answers}
    for question in state.questions_asked:
        answer = answers_by_slot.get(question["slot"], {})
        transcript_lines.append(f"Q{question['slot']}: {question['question']}")
        transcript_lines.append(
            f"A{question['slot']}: {answer.get('transcript') or '(no answer)'}"
        )
        transcript_lines.append("")

    user = f"""\
RUBRIC
{_rubric_block(rubric)}

SCORES ALREADY COMPUTED, OUT OF 100
  technical      {scores['technical']}
  communication  {scores['communication']}
  experience     {scores['experience']}
  overall        {scores['overall']}

FULL INTERVIEW TRANSCRIPT
{chr(10).join(transcript_lines).strip()}\
"""
    return EVALUATION_SYSTEM, user

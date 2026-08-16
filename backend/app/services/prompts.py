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
    PLAN_JOB_EXCERPT_CHARS,
    PLAN_KIND_MINIMUMS,
    PLAN_MAX_CONSECUTIVE_SAME_KIND,
    PLAN_MAX_FOLLOWUP_SLOTS,
    PLAN_MIN_FOLLOWUP_SLOTS,
    PLAN_RESUME_EXCERPT_CHARS,
    RUBRIC_MAX_CRITERIA,
    RUBRIC_MIN_CRITERIA,
    RUBRIC_TOTAL_POINTS,
    TURN_RESUME_ANCHOR_CAP,
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

You score the rubric twice: once from the resume alone, then again from \
the introduction alone. Each pass is a complete scoring, criterion by \
criterion in rubric order, and each produces its own total out of the \
rubric's 100 points. The two are combined afterwards, outside your answer, \
so do not try to balance them against each other or carry a number from \
one into the other.

Score the resume component first. Then score the voice component, using \
only the transcript, and judge it on its own terms: what they say they \
did, the decisions they describe making, the problems they say they hit \
and how they resolved them, and how clearly they explain any of it. A \
candidate who walks through a design decision and its tradeoff earns \
points here even where the resume only lists the tool.

For each criterion in each pass, first find the evidence, then decide the \
points. Copy each span word for word from that pass's own source. Quotes \
in the resume component are tagged 'resume' and must appear in the resume; \
quotes in the voice component are tagged 'introduction' and must appear in \
the transcript. They are checked against the originals, so copy rather \
than paraphrase. Once the evidence is in front of you, award the points it \
supports. Where that source shows nothing for a criterion, record no \
evidence and award 0.

Award points for demonstrated work: systems built and run, decisions the \
candidate made and why, problems hit and how they were handled, scale and \
constraints they worked within. Where a candidate names a technology \
without saying what they did with it, that is worth a little; where they \
describe owning and shipping something with it, that is worth much more.

Use each source for what it is good for. The resume carries structured \
facts: employers, dates, titles and tools. The introduction carries \
reasoning, ownership and how clearly the person explains their work. A \
sparse resume with a strong introduction and a dense resume with a thin \
introduction are different candidates, and scoring the two separately is \
what keeps them distinguishable.

Where the two sources disagree on a checkable fact, record it as a \
difference in neutral wording that states both versions. Report it and let \
the hiring team judge it. Differences do not change any score.

Add each component's points up and state that component's total exactly. \
Both totals are checked against their own sums.

Write the assessment for a hiring manager who has not read either source. \
Name the criteria, say what the evidence showed, and say plainly where \
each source was thin. Where the two components differ markedly, say so and \
say which way. Describe what was evidenced rather than predicting how \
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

_KIND_MINIMUM_SENTENCE = ", ".join(
    f"at least {count} '{kind}'" for kind, count in PLAN_KIND_MINIMUMS.items()
)

PLAN_SYSTEM = f"""\
You plan voice interviews. Given the role, the rubric, the candidate's \
resume and how they scored on their written application, you decide what \
each question in the interview should be for.

You are planning intent, not wording. The actual question text is written \
later, at the moment it is asked, using what the candidate has said by \
then. Your job is to make sure the interview covers the right ground in a \
sensible order.

Slot 1 is fixed: the candidate introduces themselves. Kind 'experience', \
depth 'opening'. Slot 2 asks about one specific project named on their \
resume: kind 'resume', depth 'opening', and put the project's own name in \
the anchor field.

Plan the remaining slots so every rubric criterion is probed at least once \
across the whole interview. Spend the spare slots where the screening \
evidence was thinnest: a criterion the application barely evidenced is \
worth more interview time than one already well established.

Vary the kind of question. Across the whole interview use \
{_KIND_MINIMUM_SENTENCE}, and between {PLAN_MIN_FOLLOWUP_SLOTS} and \
{PLAN_MAX_FOLLOWUP_SLOTS} 'followup' slots. Both ends of that follow-up \
range are required: fewer and the interview is a prepared list that ignores \
what the candidate says, more and it becomes one long thread about whatever \
they happened to mention first. Count your slots before you answer.

Never put more than {PLAN_MAX_CONSECUTIVE_SAME_KIND} slots of the same kind \
next to each other, and let depth build without ever dropping back. \
Interleave the kinds so the interview moves between what they have built, \
what they know, and how they work, rather than running a block of one and \
then a block of another.

Place each 'followup' after a slot whose answer is likely to be worth \
pressing on: after a project they led, or a technical claim that invites a \
"how". Slot 3 onward is fair game for one.

A workable shape, which you should adapt to this candidate rather than copy: \
1 experience opener, 2 resume, 3 technical, 4 followup, 5 experience, \
6 resume, 7 followup, 8 technical, 9 experience, 10 followup.

Anchor 'resume' slots in things their resume actually names: a project, an \
employer, a tool, a course, a competition. Copy the name as their resume \
writes it. Never invent one.

Let depth build. Use 'probing' for questions asking for specifics and \
'deep' for questions pressing on tradeoffs, failure cases and decisions \
not taken. Depth must never decrease as slots advance, and 'deep' must not \
appear before slot 4, because a candidate needs a few questions to settle \
before being pushed.

Attach one criterion to most slots, two at most where they are naturally \
probed by the same question.\
"""


def _plan_candidate_block(candidate: dict | None) -> str:
    """What the planner is allowed to anchor a resume question to.

    The planner used to see only the rubric and a column of numbers, which
    is why its questions could not name anything. It cannot ask about the
    forecasting project if nobody tells it there is one.

    The resume text is truncated rather than sent whole: a plan needs the
    shape of someone's history, and the tail of a long resume is references
    and formatting.
    """
    if not candidate:
        return "(no application on file)"

    parts: list[str] = []

    profile = candidate.get("resume_profile") or {}
    if profile:
        for entry in profile.get("experience") or []:
            line = " - ".join(
                str(v)
                for v in (entry.get("role"), entry.get("organisation"), entry.get("period"))
                if v
            )
            highlights = "; ".join(entry.get("highlights") or [])
            parts.append(f"  work: {line}" + (f" ({highlights})" if highlights else ""))
        for entry in profile.get("education") or []:
            line = " - ".join(
                str(v)
                for v in (
                    entry.get("qualification"),
                    entry.get("field_of_study"),
                    entry.get("institution"),
                    entry.get("period"),
                )
                if v
            )
            parts.append(f"  education: {line}")
        skills = ", ".join(profile.get("skills") or [])
        if skills:
            parts.append(f"  skills on resume: {skills}")

    resume_text = (candidate.get("resume_text") or "").strip()
    if resume_text:
        parts.append("\nRESUME TEXT\n" + resume_text[:PLAN_RESUME_EXCERPT_CHARS])

    intro = (candidate.get("transcript") or "").strip()
    if intro:
        parts.append("\nWHAT THEY SAID IN THEIR VOICE INTRODUCTION\n" + intro[:1200])

    return "\n".join(parts) if parts else "(no application on file)"


def plan_prompts(
    rubric,
    screening: dict | None,
    total_questions: int,
    job: dict | None = None,
) -> tuple[str, str]:
    """System and user prompt for stage 3."""
    if screening:
        thin = [
            f"  {s.get('criterion_id')}: scored "
            f"{s.get('points_awarded')} of {s.get('points_possible')}"
            for s in (screening.get("sub_scores") or [])
        ]
        matched = ", ".join(screening.get("matched_skills") or []) or "none"
        unevidenced = ", ".join(screening.get("unevidenced_skills") or []) or "none"
        screening_block = (
            f"Application score: {screening.get('screening_score')} out of 100\n"
            + "Per criterion:\n"
            + "\n".join(thin)
            + f"\nSkills their application evidenced: {matched}"
            + f"\nSkills the role asks for that it did not evidence: {unevidenced}"
        )
    else:
        screening_block = "(no screening result available)"

    if job:
        job_block = (
            f"Title: {job.get('title') or '(untitled)'}\n"
            + (f"Experience sought: {job.get('experience')}\n" if job.get("experience") else "")
            + (f"Skills sought: {', '.join(job.get('skills') or [])}\n" if job.get("skills") else "")
            + (job.get("description") or "")[:PLAN_JOB_EXCERPT_CHARS]
        )
    else:
        job_block = "(no job description available)"

    user = f"""\
Plan an interview of exactly {total_questions} questions, numbered 1 to \
{total_questions}.

THE ROLE
{job_block}

RUBRIC
{_rubric_block(rubric)}

THIS CANDIDATE
{_plan_candidate_block(screening)}

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

Then write the next question. The slot you are writing for states its \
kind, and the kind decides what the question is built from:

- 'followup': build directly on the answer you have just this moment \
scored. Take one concrete thing from it - a system they named, a number \
they gave, a decision they described, a problem they hit - and ask for the \
detail behind that specific thing. Say the thing back to them in the \
question so it is obvious you were listening: "You dropped the old index \
after the planner picked up the new one - how did you check nothing \
regressed?" is a follow-up; "Can you tell me more about your experience \
with databases?" is not, and neither is anything that would still make \
sense if the candidate had said something else entirely. Copy the claim \
you built on into anchored_on_claim. This is the only kind that continues \
the previous thread.

If the answer you just scored genuinely contains nothing concrete, do not \
manufacture a follow-up out of nothing: ask about the criteria this slot \
targets, anchored instead in something from their resume below, and leave \
anchored_on_claim null.
- 'resume': ask about the project, employer or skill named in the slot's \
anchor. Name it in the question, the way their resume names it, so it is \
plainly about them. If the anchor is empty, pick something concrete from \
the resume detail supplied below.
- 'technical': ask about a skill the role needs, on its own terms. Do not \
tie it to the previous answer. It is a new question about what they know, \
and a candidate who just described a project should now be asked something \
that stands apart from it.
- 'experience': ask how they worked. A decision and why they made it, a \
tradeoff, a disagreement with someone, something that went wrong and what \
they did about it.

Change the subject when the kind says to. A question that opens "you \
mentioned" belongs in a 'followup' slot and nowhere else. Three questions \
in a row circling the same project is the failure this is written to \
prevent, whatever the answers invite.

Concrete beats general within every kind: "How did you handle the cold \
start problem in that recommender?" rather than "Tell me about your \
experience with system design."

Keep it short. One question, phrased directly to the candidate, under 25 \
words, one thing at a time. Name the project or the detail rather than \
describing it at length: "In the Bosch diagnostic, how did you handle the \
missing months?" not "You mentioned earlier that you worked on a project \
called the Bosch diagnostic, and I was wondering whether you could \
describe how you approached the situation where some of the data was \
missing." Do not stack two questions into one sentence or add "and \
why". Ask about ground not yet covered, never re-ask something already \
answered, and do not return to a topic already discussed at length unless \
this slot is a 'followup'. The candidate hears this question spoken aloud, \
so keep it plain enough to follow by ear the first time.\
"""


def _resume_anchor_block(candidate: dict | None) -> str:
    """Concrete things from the resume a question may name.

    Supplied every turn rather than only on 'resume' slots, because the
    planner's anchor can be empty and a question that names nothing is the
    generic question this whole design exists to avoid.
    """
    if not candidate:
        return "  (none on file)"

    profile = candidate.get("resume_profile") or {}
    anchors: list[str] = []

    for entry in profile.get("experience") or []:
        label = " at ".join(
            str(v) for v in (entry.get("role"), entry.get("organisation")) if v
        )
        if label:
            anchors.append(label)
        anchors.extend((entry.get("highlights") or [])[:2])

    for entry in profile.get("education") or []:
        if entry.get("institution"):
            anchors.append(
                " ".join(
                    str(v)
                    for v in (entry.get("qualification"), entry.get("institution"))
                    if v
                )
            )

    skills = profile.get("skills") or []
    if skills:
        anchors.append("skills listed: " + ", ".join(skills[:12]))

    anchors = [a for a in anchors if a][:TURN_RESUME_ANCHOR_CAP]
    return "\n".join(f"  - {a}" for a in anchors) or "  (none on file)"

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
    # Named with their depth so a topic already gone over twice reads as
    # exhausted rather than as available ground.
    depth = getattr(state, "depth_by_topic", None) or {}
    topics = (
        ", ".join(
            f"{t} (asked about {depth.get(t, 1)}x)" for t in state.topics_discussed
        )
        or "none yet"
    )
    worn = [t for t, n in depth.items() if n >= 2]
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

TOPICS ALREADY COVERED ENOUGH, DO NOT RETURN TO THESE
{", ".join(worn) or "none yet"}

CLAIMS THE CANDIDATE HAS MADE
{claims}\
"""


def _slot_block(label: str, slot) -> str:
    if slot is None:
        return f"{label}\n  (none)"
    lines = [
        label,
        f"  slot {slot.slot}, kind {slot.kind}, depth {slot.depth}",
        f"  intent: {slot.intent}",
        f"  criteria: {', '.join(slot.criterion_ids)}",
    ]
    if getattr(slot, "anchor", None):
        lines.append(f"  anchor: {slot.anchor}")
    return "\n".join(lines)


def turn_prompts(
    rubric, answered_slot, next_slot, state, answer: str, candidate: dict | None = None
) -> tuple[str, str]:
    """System and user prompt for a mid-interview turn."""
    user = f"""\
RUBRIC
{_rubric_block(rubric)}

{_state_block(state)}

RESUME DETAIL YOU MAY NAME IN A QUESTION
{_resume_anchor_block(candidate)}

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


# ---------------------------------------------------------------------
# Stage 0: job description parsing. Feeds the Create Job form.
# ---------------------------------------------------------------------
#
# Not a scoring stage. This one only fills in a form HR is about to review
# and edit, so the cost of a wrong answer is different from the rest of
# the pipeline: a bad rubric produces bad scores, whereas a bad extraction
# produces a field HR corrects in two seconds. What it must never do is
# invent a fact that looks plausible enough not to get corrected.

JOB_FACTS_SYSTEM = """\
You read a job description document and pull out the facts a hiring form \
needs. You are a careful reader, not a writer: everything you return has \
to be traceable to something the document actually says.

The one rule that matters: if the document does not state something, \
return null for it. Do not infer a salary band from the seniority. Do not \
infer remote or onsite from the presence of an office address, because \
plenty of onsite-sounding roles are hybrid and the document has simply not \
said. Do not guess a department from the team's subject matter. A null \
field costs the recruiter one moment of typing; a confidently wrong one \
gets published to candidates because it looked right.

Say what the document says. Where it gives a number, a place or a title, \
copy it in the document's own words rather than paraphrasing it into \
something tidier. "18 to 24 LPA" stays "18 to 24 LPA".

For the description body, keep the responsibilities and what the team is \
looking for, and keep the document's voice. Drop the parts a hiring form \
does not need: how to apply, equal-opportunity boilerplate, the company's \
awards, and anything you have already returned as a separate field.

For skills, list the concrete tools, languages and technologies a resume \
would name: SQL, Power BI, Python, Tableau, Excel. Leave out dispositions \
like "self-motivated" or "team player". Those matter for the role, but \
they are scored from what a candidate says about their work, not matched \
against a keyword.\
"""


def job_facts_prompts(document_text: str) -> tuple[str, str]:
    """System and user prompt for parsing an uploaded job description."""
    user = f"""\
Pull the hiring facts out of this job description.

JOB DESCRIPTION DOCUMENT
{document_text}\
"""
    return JOB_FACTS_SYSTEM, user


# ---------------------------------------------------------------------
# Resume profile. Feeds Candidate Detail, never a score.
# ---------------------------------------------------------------------
#
# Kept deliberately separate from screening. Screening reads the raw
# resume text against the rubric and is the only stage that produces a
# number. This one exists so HR can see who they are looking at without
# reading a wall of extracted text.

RESUME_PROFILE_SYSTEM = """\
You read a resume and lay out what it says. You are a careful reader, not \
an evaluator: you do not judge the candidate, rank them, or comment on \
whether they are suitable for anything. Someone else scores this person \
against a rubric, and they read the original text, not your summary.

Copy, do not compute. Dates, grades, titles and institution names go in \
exactly as the resume writes them. If a resume says "2023 - 2027", that is \
the period; do not turn it into "4 years" or work out a graduation year. If \
it gives no dates for a role, the period is null. A date you calculated is \
indistinguishable from one the candidate wrote, and this is attached to a \
named person.

Return null, or an empty list, for anything absent. A sparse resume is a \
real resume, not a failure, and a null field is honest where a guess is \
not.

Separate work from projects. Jobs, internships and substantial positions \
of responsibility are experience. Course projects and personal builds are \
not, however impressive: they stay in the resume text where the screening \
stage reads them.

For highlights, take what the person actually did, in the resume's own \
words, preferring bullets that name a concrete task, tool or result over \
ones that describe a responsibility in the abstract. "Built Power BI \
dashboards that cut manual analysis time by 40%" over "Responsible for \
reporting and stakeholder engagement".\
"""


def resume_profile_prompts(resume_text: str) -> tuple[str, str]:
    """System and user prompt for structuring one resume."""
    user = f"""\
Lay out what this resume says.

RESUME TEXT
{resume_text}\
"""
    return RESUME_PROFILE_SYSTEM, user

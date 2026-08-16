"""Pydantic schemas for every LLM stage, plus the API request/response
shapes built from them.

These models are handed to Gemini as `response_schema`, so two things about
them are load-bearing:

1. **Field order is generation order.** The model fills fields in the order
   they are declared. Where one field should inform another, the informing
   field is declared first (see TurnResult in backend.md 5.4).
2. **Field descriptions are prompt.** Gemini reads them. A description that
   says what good input looks like measurably improves output, so they are
   written for the model, not just for the next developer.

Stages land phase by phase (docs/implementation-plan.md). Rubric models are
here now; screening and interview models arrive in Phases 3 and 4.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------
# Stage 1: rubric generation. backend.md 5.1
# ---------------------------------------------------------------------


class Criterion(BaseModel):
    """One scoring criterion with an explicit point allocation."""

    id: str = Field(
        description=(
            "Stable lowercase slug, words joined by underscores, derived from "
            "the criterion name. For example python_and_django, sql_modelling, "
            "system_design. Must be unique within the rubric."
        )
    )
    name: str = Field(
        description="Short human readable name, two to five words, in sentence case."
    )
    description: str = Field(
        description=(
            "One or two sentences stating what concrete evidence earns points "
            "for this criterion. Name the specific things a strong candidate "
            "would mention: technologies, scale, ownership, decisions made. "
            "This text is reused later to score real candidates, so write it "
            "as scoring guidance rather than as a job advert."
        )
    )
    points: int = Field(
        description=(
            "Whole number of points allocated to this criterion. Points across "
            "all criteria must total exactly 100. Weight criteria by how much "
            "they actually matter for this role."
        )
    )
    dimension: Literal["technical", "communication", "experience"] = Field(
        description=(
            "Which of the three reported dimensions this criterion belongs to. "
            "Use technical for hands-on skill with tools, languages, systems "
            "and design. Use communication for explaining work, writing, "
            "mentoring, collaboration and stakeholder handling. Use experience "
            "for track record: years, seniority, domain exposure, ownership of "
            "shipped work. Every rubric needs at least one criterion in each "
            "of the three."
        )
    )


class Rubric(BaseModel):
    """The contract. Every downstream score is computed against this and
    nothing else - see CLAUDE.md "Core rule"."""

    criteria: list[Criterion] = Field(
        description=(
            "Between 4 and 7 criteria covering the distinct capabilities this "
            "role requires. Each criterion should be assessable from what a "
            "candidate says about their experience. Prefer criteria about "
            "demonstrable skill and applied experience."
        )
    )
    interview_topics: list[str] = Field(
        description=(
            "Three to six short topics worth probing in a live interview, "
            "phrased as subject areas rather than as questions."
        )
    )

    def criterion_ids(self) -> set[str]:
        return {c.id for c in self.criteria}

    def total_points(self) -> int:
        return sum(c.points for c in self.criteria)

    def by_id(self, criterion_id: str) -> Criterion | None:
        for criterion in self.criteria:
            if criterion.id == criterion_id:
                return criterion
        return None

    def by_dimension(self, dimension: str) -> list[Criterion]:
        return [c for c in self.criteria if c.dimension == dimension]


# ---------------------------------------------------------------------
# Stage 3: interview plan. backend.md 5.3
# ---------------------------------------------------------------------


class PlannedQuestion(BaseModel):
    """One slot in the interview plan.

    The plan is generated once, before the first question, and never
    changes. What adapts is the *wording* of each question, produced at the
    moment it is asked from the interview state. The plan guarantees the
    interview covers the whole rubric; the state guarantees each question
    is specific to what the candidate actually said.
    """

    slot: int = Field(description="Position in the interview, starting at 1.")
    # Chosen before the intent, so the intent is written to serve a decided
    # kind of question rather than the kind being labelled after the fact.
    kind: Literal["resume", "technical", "experience", "followup"] = Field(
        description=(
            "What sort of question this slot is. 'resume' asks about a "
            "specific project, employer or skill named on their resume. "
            "'technical' tests a skill the role needs, independent of their "
            "history. 'experience' asks how they worked: a decision they "
            "made, a tradeoff, a disagreement, something that went wrong. "
            "'followup' presses on whatever they said in the previous "
            "answer, and is the only kind that depends on the previous "
            "answer. Vary these: an interview that repeats one kind tests "
            "one facet of a person over and over."
        )
    )
    intent: str = Field(
        description=(
            "One short sentence stating what this question is for, written for "
            "the interviewer rather than the candidate. For example 'Probe how "
            "they handled query performance at scale'."
        )
    )
    anchor: str | None = Field(
        default=None,
        description=(
            "For a 'resume' slot, the exact project, employer, tool or skill "
            "from their resume this question is about, named as their resume "
            "names it, so the question can mention it. Null for every other "
            "kind. Never invent one: if their resume does not name it, it "
            "does not go here."
        ),
    )
    criterion_ids: list[str] = Field(
        description=(
            "The rubric criterion ids this slot is meant to probe, copied "
            "exactly. Usually one, at most two."
        )
    )
    depth: Literal["opening", "probing", "deep"] = Field(
        description=(
            "opening for the first two orienting questions, probing for "
            "questions that ask for specifics, deep for questions that press "
            "on tradeoffs and edge cases. Depth may not decrease as slots "
            "advance, and deep may not appear before slot 4."
        )
    )


class InterviewPlan(BaseModel):
    questions: list[PlannedQuestion] = Field(
        description=(
            "One entry per slot, in order, starting at slot 1. Slot 1 is a "
            "fixed opener asking the candidate to introduce themselves, kind "
            "'experience'. Slot 2 asks about a specific project named on "
            "their resume, kind 'resume'. Plan the remaining slots so that "
            "every rubric criterion is probed at least once across the whole "
            "interview, spending the extra slots on criteria where the "
            "screening evidence was thin, and so that the kinds vary rather "
            "than running in a block."
        )
    )

    def slot(self, number: int) -> PlannedQuestion | None:
        for question in self.questions:
            if question.slot == number:
                return question
        return None


# ---------------------------------------------------------------------
# Stage 4: turn result. backend.md 5.4
# ---------------------------------------------------------------------


class AnswerScore(BaseModel):
    """Points for one criterion, from a single answer.

    Same field ordering rule as SubScore: evidence before points, so the
    quote is found before the number is chosen.
    """

    criterion_id: str = Field(description="Criterion being scored, copied exactly.")
    evidence: str = Field(
        description=(
            "One continuous span copied word for word from this answer, "
            "supporting the points below. Leave empty only when awarding 0."
        )
    )
    points_awarded: int = Field(
        description="Whole number from 0 to points_possible, justified by the evidence."
    )
    points_possible: int = Field(
        description="Points this criterion is worth in the rubric, copied exactly."
    )


class AnswerAnalysis(BaseModel):
    """Everything learned from the answer that just arrived.

    Used on its own for the final turn, where there is no next question to
    generate, and inherited by TurnResult for every other turn.
    """

    answer_scores: list[AnswerScore] = Field(
        description=(
            "Score this answer against the criteria the question was meant to "
            "probe. One entry per criterion probed. Award 0 where the answer "
            "did not address it."
        )
    )
    topics_identified: list[str] = Field(
        description=(
            "Short topic labels for what this answer was about, two to five "
            "words each, for example 'recommender systems' or 'query "
            "optimisation'."
        )
    )
    claims_made: list[str] = Field(
        description=(
            "Specific factual claims the candidate made that are worth probing "
            "later, one sentence each. For example 'Built a recommendation "
            "system using collaborative filtering'. These become the anchors "
            "for later follow-up questions, so prefer concrete, checkable "
            "claims over general statements."
        )
    )


class TurnResult(AnswerAnalysis):
    """Scoring and extraction, then the next question.

    Field order is load-bearing and inherited deliberately: everything in
    AnswerAnalysis is generated first, so the model has assessed the answer
    before it decides what to ask next. A weak answer should produce a
    follow-up that presses; a strong one should move on.
    """

    next_question: str = Field(
        description=(
            "The next question, as a single direct question under 30 words, "
            "addressed to the candidate. Ask about the criteria this slot "
            "targets. Where the candidate has made a related claim, anchor the "
            "question to that specific claim and ask for a concrete detail "
            "about it, for example 'How did you handle the cold start problem "
            "in that recommender?'. Ask about something not yet covered, and "
            "do not repeat a question already asked."
        )
    )
    targets_criterion_ids: list[str] = Field(
        description="The rubric criterion ids this question probes, copied exactly."
    )
    anchored_on_claim: str | None = Field(
        default=None,
        description=(
            "The earlier claim this question builds on, copied from "
            "claims_made, or null when the question does not build on one."
        ),
    )


# ---------------------------------------------------------------------
# Stage 5: evaluation. backend.md 5.5
# ---------------------------------------------------------------------


class Evaluation(BaseModel):
    """The narrative half of the interview result.

    The three dimension scores and the overall are computed in Python from
    the accumulated AnswerScore rows and handed to the model. It does not
    invent them; it writes strengths, concerns and a recommendation against
    numbers that were already derived from evidence.
    """

    strengths: list[str] = Field(
        description=(
            "Two to four complete sentences, each naming something the "
            "candidate actually said and why it counted. Quote or closely "
            "paraphrase their own words rather than describing them in the "
            "abstract."
        )
    )
    concerns: list[str] = Field(
        description=(
            "One to four complete sentences on what the interview did not "
            "evidence, each pointing at a specific gap. Describe what was "
            "missing from the answers rather than predicting how the person "
            "would perform."
        )
    )
    recommendation: Literal["shortlist", "review", "reject"] = Field(
        description=(
            "Your call given the scores and the transcript: shortlist for a "
            "strong showing, review when it was mixed, reject when the answers "
            "showed little of what the rubric asks for."
        )
    )


# ---------------------------------------------------------------------
# Stage 2: screening. backend.md 5.2
# ---------------------------------------------------------------------


class Evidence(BaseModel):
    """One verbatim span supporting a score, tagged with where it came from."""

    source: Literal["introduction", "resume"] = Field(
        description=(
            "Which document this quote came from. Use introduction for the "
            "spoken transcript and resume for the uploaded resume text. The "
            "quote is checked against that document, so tagging it wrongly is "
            "treated as a failure."
        )
    )
    quote: str = Field(
        description=(
            "One continuous span copied word for word from that source. Copy "
            "it exactly, including wording and spelling, and keep it under "
            "about 30 words. Quote a single unbroken passage: do not stitch "
            "separate sentences together with an ellipsis. When a criterion "
            "is supported in two different places, add a second evidence "
            "entry instead of joining them."
        )
    )


class SubScore(BaseModel):
    """Points for one rubric criterion.

    Field order is load-bearing and differs deliberately from the order
    written in backend.md 5.2. `evidence` is declared before
    `points_awarded` so the model has to locate real supporting quotes
    before it commits to a number. Declaring points first lets it pick a
    score and then look for justification, which is the mechanism behind
    the 15 to 20 point drift described in CLAUDE.md.
    """

    criterion_id: str = Field(
        description="The id of the rubric criterion being scored, copied exactly."
    )
    evidence: list[Evidence] = Field(
        description=(
            "The quotes that justify the points you are about to award. Gather "
            "these first. Include one for each distinct thing the candidate "
            "showed for this criterion. Leave this empty only when the sources "
            "contain nothing relevant, in which case award 0 points."
        )
    )
    points_awarded: int = Field(
        description=(
            "Whole number of points earned, from 0 to points_possible, "
            "justified by the evidence above. Award points for what the "
            "evidence actually demonstrates."
        )
    )
    points_possible: int = Field(
        description="The points this criterion is worth in the rubric, copied exactly."
    )


class Screening(BaseModel):
    """Result of scoring one candidate against the rubric.

    Two components, scored in one pass against the same rubric.

    The resume and the introduction answer different questions. A resume
    carries structured facts - employers, dates, titles, tools - that a
    two minute spoken introduction never will. The introduction carries
    reasoning, ownership and how clearly someone explains their own work,
    which a resume cannot show at all. Rolling both into one number let a
    polished CV carry a candidate who could not describe anything they had
    built, and the reverse.

    So each source is scored against the whole rubric on its own, giving
    two independent 0 to 100 figures, and Python weights them into the
    final score (SCREENING_RESUME_WEIGHT / SCREENING_VOICE_WEIGHT). The
    rubric itself is untouched: it still totals exactly 100, and each
    component is a full scoring of it.

    Field order is load-bearing throughout: the resume component is
    generated before the voice component, and within each, evidence comes
    before points.
    """

    sub_scores: list[SubScore] = Field(
        description=(
            "The RESUME component. Exactly one entry for every criterion in "
            "the rubric, in rubric order, scored from the resume text alone. "
            "Every evidence quote here must be tagged 'resume' and must come "
            "from the resume. Score every criterion even when the resume says "
            "nothing about it; award 0 with no evidence where it does not."
        )
    )
    total_score: int = Field(
        description=(
            "The sum of every points_awarded in the resume component above. "
            "Add them up and state the total exactly; it is checked."
        )
    )
    voice_sub_scores: list[SubScore] = Field(
        description=(
            "The VOICE component. The same rubric again, scored from the "
            "spoken introduction alone, one entry per criterion in rubric "
            "order. Every evidence quote here must be tagged 'introduction' "
            "and must come from the transcript. This is where reasoning, "
            "ownership and clarity of explanation earn points: a candidate "
            "who describes a decision they made and why scores here even "
            "where the resume only lists the tool. Award 0 with no evidence "
            "where the introduction does not address a criterion."
        )
    )
    voice_total_score: int = Field(
        description=(
            "The sum of every points_awarded in the voice component above. "
            "Add them up and state the total exactly; it is checked."
        )
    )
    matched_skills: list[str] = Field(
        description=(
            "Required skills that either source clearly evidences, named as "
            "they appear in the required skills list."
        )
    )
    unevidenced_skills: list[str] = Field(
        description=(
            "Required skills neither source mentions. This records what the "
            "documents did not cover, not a judgement that the candidate "
            "lacks the skill."
        )
    )
    resume_intro_conflicts: list[str] = Field(
        description=(
            "Places where the resume and the introduction disagree on a "
            "checkable fact, such as differing tenure at an employer. Write "
            "each as one neutral sentence stating both versions, for example "
            "'The resume lists 3 years at Zoho, the introduction said 5 "
            "years.' Report the difference without judging it, and do not let "
            "it change any score. Leave empty when they agree."
        )
    )
    assessment: str = Field(
        description=(
            "Three to five sentences for the hiring team on what the evidence "
            "showed against the rubric, naming specific criteria. Describe "
            "what was and was not evidenced rather than predicting whether "
            "the person would succeed."
        )
    )
    recommendation: Literal["shortlist", "review", "reject"] = Field(
        description=(
            "Your call given the total and the evidence: shortlist for a "
            "strong match, review when the evidence is mixed or thin, reject "
            "when the sources show little of what the rubric asks for."
        )
    )


# ---------------------------------------------------------------------
# Candidate portal. What an applicant may see about their own application.
# ---------------------------------------------------------------------
#
# The candidate never sees a score, at any point, including on completion
# (product.md section 2). This is the single most likely place in the API
# for one to leak, because it is the only candidate-facing response built
# from a candidate row, and that row carries screening_score,
# screening_band, recommendation, sub_scores and assessment.
#
# The defence is that this model is built field by field from an explicit
# whitelist, never by copying a row or spreading another model. A test
# asserts the serialized response contains none of those keys.


class CandidateApplication(BaseModel):
    """One application, as the person who submitted it may see it."""

    candidate_id: str
    job_id: str
    job_title: str
    applied_at: str

    # A coarser vocabulary than the internal candidate state on purpose.
    # `rejected` and `screened` are words for the hiring team; a candidate
    # is told their application is closed, not that it scored 42.
    status: Literal[
        "submitted", "in_review", "interview_ready", "interview_in_progress",
        "interview_complete", "closed",
    ]
    status_label: str
    status_detail: str

    # Present only once HR has sent the invitation, and withdrawn once the
    # interview is finished so a completed link cannot be reopened from
    # here.
    interview_url: str | None = None


# ---------------------------------------------------------------------
# Resume profile. Structured facts for Candidate Detail.
# ---------------------------------------------------------------------
#
# Not a scoring stage, and deliberately kept away from one. Screening reads
# the raw resume text against the rubric and is the only thing that
# produces a number. This exists so HR can see who they are looking at
# without reading a wall of extracted text, and nothing here feeds a score.


class EducationEntry(BaseModel):
    institution: str = Field(description="School or university, as written.")
    qualification: str | None = Field(
        default=None,
        description="Degree or certificate, for example 'B.Tech' or 'Class XII'. Null if unstated.",
    )
    field_of_study: str | None = Field(
        default=None,
        description="Subject, for example 'Computer Science'. Null if unstated.",
    )
    period: str | None = Field(
        default=None,
        description=(
            "Dates exactly as the resume writes them, for example '2023 - 2027' "
            "or 'Aug 2023 to Aug 2027'. Null when no dates are given. Do not "
            "compute or complete a range the resume left open."
        )
    )
    result: str | None = Field(
        default=None,
        description=(
            "Grade as written, for example 'CGPA 8.78' or '92.4%'. Null if "
            "the resume does not state one."
        )
    )


class ExperienceEntry(BaseModel):
    organisation: str = Field(description="Employer or organisation, as written.")
    role: str | None = Field(
        default=None,
        description="Job title, for example 'Data Science Intern'. Null if unstated.",
    )
    period: str | None = Field(
        default=None,
        description=(
            "Dates exactly as written, for example 'June to August 2026'. Null "
            "when the resume gives none."
        )
    )
    highlights: list[str] = Field(
        description=(
            "Up to three of what this person actually did in this role, each a "
            "short phrase taken from the resume's own bullets. Prefer the ones "
            "naming a concrete task, tool or result over the ones describing a "
            "responsibility in the abstract."
        )
    )


class ResumeProfile(BaseModel):
    """A structured reading of one resume.

    Every field is optional or a list that may be empty, because resumes
    vary enormously and a sparse one is a real resume rather than a
    failure. Nothing here is inferred: if the document does not state a
    graduation year, the field is null rather than computed from context.
    A fabricated date attached to a named person is worse than a gap.
    """

    headline: str | None = Field(
        default=None,
        description=(
            "One line describing what this person is, in your own words but "
            "grounded only in the resume, for example 'Final year computer "
            "science student with analytics internships'. Under 15 words. "
            "Null if the resume is too sparse to characterise."
        )
    )
    education: list[EducationEntry] = Field(
        description="Every education entry, most recent first. Empty if none appear."
    )
    experience: list[ExperienceEntry] = Field(
        description=(
            "Jobs, internships and substantial positions of responsibility, "
            "most recent first. Leave out course projects, which belong to "
            "the resume text rather than to a work history. Empty if none."
        )
    )
    skills: list[str] = Field(
        description=(
            "Tools, languages and technologies the resume names, as it names "
            "them. Up to 20. These are for orientation only and are never "
            "matched against the rubric: that is screening's job, and it "
            "reads the resume text directly."
        )
    )
    links: list[str] = Field(
        description=(
            "URLs the resume gives, for example a GitHub or portfolio. Copy "
            "them exactly. Empty when the resume has none or gives only "
            "unlinked labels."
        )
    )


# ---------------------------------------------------------------------
# HR accounts. database/002_accounts.sql
# ---------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    company: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class HRAccount(BaseModel):
    """The signed-in account as the frontend sees it.

    Carries no password hash, no salt and no session token. The token is
    returned once by SessionResponse at sign in and never again, so a
    component that re-reads the account cannot accidentally re-expose it.
    """

    id: str
    email: str
    name: str
    company: str | None = None


class SessionResponse(BaseModel):
    """The one response that carries the bearer token."""

    token: str
    expires_at: str
    account: HRAccount
    # How many pre-existing ownerless jobs this account just claimed. Only
    # ever non-zero for the first account, and shown once so the claim is
    # visible rather than silent.
    claimed_jobs: int = 0


# ---------------------------------------------------------------------
# API shapes for the jobs routes. backend.md section 4
# ---------------------------------------------------------------------


class JobCreate(BaseModel):
    title: str
    description: str
    skills: list[str] = []
    experience: str | None = None
    # Real columns since database/002_accounts.sql. These used to be
    # appended to the description string by the frontend, which meant they
    # could never be read back out or shown to a candidate as fields.
    department: str | None = None
    location: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    compensation: str | None = None


class JobFacts(BaseModel):
    """Structured facts pulled out of an uploaded job description.

    Every field except `skills` and `description` is optional, and the
    prompt is told to return null rather than guess. A job description
    that does not state a salary must not produce an invented one: HR is
    about to publish this to candidates, and a fabricated compensation
    range is worse than an empty field they fill in themselves.

    Field order is generation order (see the module docstring), so the
    description body is produced last, after the facts it has to have
    removed from it.
    """

    title: str | None = Field(
        default=None,
        description=(
            "The role title exactly as the document states it, for example "
            "'Junior Business Analyst'. Null if the document never names the "
            "role."
        )
    )
    department: str | None = Field(
        default=None,
        description="Team or department, if stated. Null otherwise.",
    )
    location: str | None = Field(
        default=None,
        description=(
            "Work location as written, for example 'Hyderabad' or "
            "'Bangalore, India'. Null if the document does not say."
        )
    )
    workplace_type: Literal["remote", "hybrid", "onsite"] | None = Field(
        default=None,
        description=(
            "Only when the document actually says so. A named office "
            "location alone is not enough to conclude onsite: many onsite "
            "roles are hybrid and the document simply has not said. Null "
            "when it is not stated."
        )
    )
    employment_type: Literal["full_time", "part_time", "contract", "internship"] | None = Field(
        default=None,
        description=(
            "Only when stated or unambiguous from the title, for example a "
            "title containing 'Intern' means internship. Null otherwise."
        )
    )
    compensation: str | None = Field(
        default=None,
        description=(
            "The pay as written, for example '18 to 24 LPA' or '$120k to "
            "$150k'. Null when the document does not state pay. Never "
            "estimate a range from the seniority or the location."
        )
    )
    skills: list[str] = Field(
        description=(
            "Concrete skills, tools and technologies the document asks for, "
            "each as it would appear on a resume: 'SQL', 'Power BI', "
            "'Python'. Between 3 and 10. Leave out soft qualities like "
            "'team player', which the rubric handles separately."
        )
    )
    experience: str | None = Field(
        default=None,
        description=(
            "The experience requirement as a short phrase, for example "
            "'0 to 2 years' or 'Final year student'. Null if unstated."
        )
    )
    description: str = Field(
        description=(
            "The body of the posting: what the role does, the "
            "responsibilities, and what the team is looking for. Keep the "
            "document's own wording. Leave out the facts already captured "
            "in the fields above, and leave out boilerplate about how to "
            "apply or equal-opportunity statements."
        )
    )


class JobDescriptionDocument(BaseModel):
    """Extracted source text for HR to review before posting a role.

    `facts` is null when parsing failed. The raw text is still returned in
    that case so the upload remains useful: HR pastes it into the
    description and fills the rest in by hand, which is exactly the
    behavior that existed before parsing was added.
    """

    text: str
    facts: JobFacts | None = None


class JobSummary(BaseModel):
    """Row shape for the Jobs Dashboard (screens.md section 1)."""

    id: str
    title: str
    state: str
    created_at: str
    applicant_count: int = 0
    shortlisted_count: int = 0
    interviewed_count: int = 0


class JobDetail(BaseModel):
    """Full job including the rubric, for Create Job stage C and Job
    Detail (screens.md sections 2 and 3)."""

    id: str
    title: str
    description: str
    skills: list[str]
    experience: str | None
    state: str
    created_at: str
    rubric: Rubric | None
    department: str | None = None
    location: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    compensation: str | None = None
    applicant_count: int = 0
    shortlisted_count: int = 0
    interviewed_count: int = 0


class PublicJobSummary(BaseModel):
    """A public role view. It intentionally excludes the scoring rubric."""

    id: str
    title: str
    state: str
    description: str
    skills: list[str]
    experience: str | None
    created_at: str
    # Shown on the opportunity page. These are the questions a candidate
    # asks before deciding whether to record a two minute introduction.
    department: str | None = None
    location: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    compensation: str | None = None
    # Whether the caller has already applied, answered only when they say
    # who they are. False for an anonymous browse, which is honest: nobody
    # has applied as nobody.
    #
    # It is a property of the request, not of the job, and it is the same
    # fact the unique constraint on (job_id, email) enforces at insert
    # time. Explore reads it so the portal cannot drift from what applying
    # would actually do.
    applied: bool = False


class CandidateCreated(BaseModel):
    """Response to a submitted application.

    Deliberately carries no score, band or recommendation. The candidate
    never sees their result (product.md section 2), so it is not sent to
    the browser at all rather than being sent and hidden.
    """

    id: str
    job_title: str


class EvidenceOut(BaseModel):
    source: str
    quote: str


class SubScoreOut(BaseModel):
    """A scored criterion joined to its rubric name, so the HR breakdown
    can show 'SQL and data modelling 14 / 20' without the frontend having
    to look names up in the rubric itself."""

    criterion_id: str
    criterion_name: str
    points_awarded: int
    points_possible: int
    evidence: list[EvidenceOut]


class CandidateSummary(BaseModel):
    """Row shape for the ranked list on Job Detail (screens.md section 3)."""

    id: str
    name: str
    email: str
    screening_score: int | None
    screening_band: str | None
    recommendation: str | None
    matched_count: int
    skills_total: int
    state: str
    created_at: str
    # The interview, when there is one. Job Detail leads with candidates who
    # have been interviewed, and it cannot rank them without their score.
    interview_status: str | None = None
    interview_score: int | None = None
    interview_band: str | None = None
    # Which role this applicant is for. Redundant on Job Detail, which
    # already knows, and the whole point of the cross-role directory, which
    # would otherwise have to fetch each job separately to label a row.
    job_id: str | None = None
    job_title: str | None = None


class CandidateDetail(BaseModel):
    """Everything Candidate Detail renders (screens.md section 4)."""

    id: str
    job_id: str
    job_title: str
    name: str
    email: str
    state: str
    created_at: str

    screening_score: int | None
    screening_band: str | None
    recommendation: str | None
    # The two components behind screening_score, each a full 0-100 scoring
    # of the same rubric. Null on rows screened before the split, which the
    # screen renders as "not recorded" rather than as zero.
    resume_score: int | None = None
    voice_score: int | None = None
    sub_scores: list[SubScoreOut]
    voice_sub_scores: list[SubScoreOut] = []
    matched_skills: list[str]
    unevidenced_skills: list[str]
    resume_intro_conflicts: list[str]
    assessment: str | None

    transcript: str | None
    audio_url: str | None
    resume_url: str | None
    resume_text: str | None

    interview_status: str | None = None
    interview_token: str | None = None


# ---------------------------------------------------------------------
# Interview API shapes
# ---------------------------------------------------------------------


class InterviewSession(BaseModel):
    """Drives which stage the candidate screen renders (screens.md 7).

    Carries no score, band or recommendation: the candidate never sees
    their result, so it is not sent to the browser at all.
    """

    status: str
    job_title: str
    candidate_name: str
    total_questions: int | None
    current_slot: int | None
    current_question: str | None


class TurnAdvanced(BaseModel):
    """Response to a submitted answer."""

    status: str
    next_slot: int | None = None
    next_question: str | None = None
    total_questions: int | None = None


class InterviewTurnOut(BaseModel):
    slot: int
    question: str
    answer_text: str | None
    criteria: list[str]
    response_time_seconds: int | None
    audio_url: str | None


class InterviewResult(BaseModel):
    """HR-facing result (screens.md section 5)."""

    candidate_id: str
    candidate_name: str
    job_title: str
    status: str
    total_questions: int | None
    completed_at: str | None

    overall_score: int | None
    technical_score: int | None
    communication_score: int | None
    experience_score: int | None
    band: str | None
    strengths: list[str]
    concerns: list[str]
    recommendation: str | None

    turns: list[InterviewTurnOut]


class ApprovalResult(BaseModel):
    """Returned when HR approves a candidate for interview."""

    candidate_id: str
    state: str
    interview_token: str
    interview_path: str

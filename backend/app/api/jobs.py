"""Job routes. backend.md section 4.

Rubric generation runs synchronously inside POST /jobs. It takes 3 to 8
seconds and the request holds open for it, which is correct at this scale
and removes an entire category of failure (backend.md section 1). The
frontend shows "Analyzing job description" for the duration - a single
real state, not fake sub-steps (screens.md section 2 stage B).
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends, File, UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.auth import HRUser, require_hr
from app.core.errors import (
    JobDescriptionTooLarge,
    JobDescriptionUnreadable,
    JobDescriptionWrongFormat,
    JobNotActive,
    RubricGenerationFailed,
)
from app.core.heuristics import RUBRIC_GENERATION_MAX_RETRIES
from app.integrations import storage
from app.integrations.llm import generate_structured
from app.models import (
    JobCreate,
    JobDescriptionDocument,
    JobDetail,
    JobFacts,
    JobSummary,
    PublicJobSummary,
    Rubric,
)
from app.services.accounts import normalise_email
from app.services.prompts import job_facts_prompts, rubric_prompts
from app.services.validation import validate_job_facts, validate_rubric

logger = logging.getLogger("rubric.api.jobs")

router = APIRouter(tags=["jobs"])

_JOB_DOCUMENT_MAX_BYTES = 10 * 1024 * 1024


def _job_document_text(data: bytes) -> str:
    """Read a supplied job-description PDF without persisting the upload.

    The HR user always gets the extracted copy in the editable description
    field before creating a job. That preserves review and control; the PDF
    is an input aid, not an opaque source of truth.
    """
    if not data:
        raise JobDescriptionWrongFormat("That PDF is empty. Upload a job description with text.")
    if len(data) > _JOB_DOCUMENT_MAX_BYTES:
        raise JobDescriptionTooLarge()
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except (PdfReadError, ValueError):
        raise JobDescriptionWrongFormat() from None
    except Exception:
        logger.warning("job description PDF extraction failed", exc_info=True)
        raise JobDescriptionUnreadable() from None
    if len(text) < 40:
        raise JobDescriptionUnreadable()
    return text


def _generate_rubric(
    title: str, description: str, skills: list[str], experience: str | None
) -> Rubric:
    system, user = rubric_prompts(title, description, skills, experience)
    return generate_structured(
        system,
        user,
        Rubric,
        validate=validate_rubric,
        max_retries=RUBRIC_GENERATION_MAX_RETRIES,
    )


def _to_detail(row: dict, counts: dict[str, int] | None = None) -> JobDetail:
    counts = counts or {"applicant": 0, "shortlisted": 0, "interviewed": 0}
    raw_rubric = row.get("rubric")
    return JobDetail(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        skills=row.get("skills") or [],
        experience=row.get("experience"),
        state=row["state"],
        created_at=row["created_at"],
        rubric=Rubric.model_validate(raw_rubric) if raw_rubric else None,
        department=row.get("department"),
        location=row.get("location"),
        workplace_type=row.get("workplace_type"),
        employment_type=row.get("employment_type"),
        compensation=row.get("compensation"),
        applicant_count=counts["applicant"],
        shortlisted_count=counts["shortlisted"],
        interviewed_count=counts["interviewed"],
    )


_FACT_COLUMNS = ("department", "location", "workplace_type", "employment_type", "compensation")


def _applied_job_ids(email: str | None) -> set[str]:
    """Jobs this address has already applied to.

    One query, and the same relationship the database enforces: applying
    twice violates the unique constraint on (job_id, email) and comes back
    as `already_applied`. Reading it here means the portal can only ever
    offer roles that applying would actually accept.

    Deliberately not routed through the DEMO_AUTH fallback used by the
    applications list. That fallback widens an empty answer to every
    application on file, which here would hide every open role from a
    candidate who has applied to none.
    """
    if not email or not email.strip():
        return set()
    rows = storage.list_candidates_by_email(normalise_email(email))
    return {row["job_id"] for row in rows}


def _to_public(row: dict, applied: bool = False) -> PublicJobSummary:
    """The candidate-facing view of a job. Never carries the rubric, which
    would tell an applicant exactly what to say."""
    return PublicJobSummary(
        applied=applied,
        id=row["id"],
        title=row["title"],
        state=row["state"],
        description=row["description"],
        skills=row.get("skills") or [],
        experience=row.get("experience"),
        created_at=row["created_at"],
        department=row.get("department"),
        location=row.get("location"),
        workplace_type=row.get("workplace_type"),
        employment_type=row.get("employment_type"),
        compensation=row.get("compensation"),
    )


def _job_facts_columns(payload: JobCreate) -> dict:
    """The optional job facts, blanks dropped.

    An empty string from a form field is not a value, it is an untouched
    input, so it is left out entirely rather than written as "". That
    keeps "not stated" as a single representation instead of two that the
    UI would then have to test for separately.
    """
    values = {}
    for column in _FACT_COLUMNS:
        raw = getattr(payload, column, None)
        if raw and str(raw).strip():
            values[column] = str(raw).strip()
    return values


def owned_job_or_404(job_id: str, hr: HRUser) -> dict:
    """Fetch a job the signed-in account owns, or refuse.

    404 rather than 403 on someone else's job. A 403 confirms the id
    exists, which turns this route into an oracle for enumerating other
    accounts' job ids. From outside, "not yours" and "not there" should be
    indistinguishable.

    Every HR route that takes a job_id goes through here. Adding a route
    that reads storage.get_job directly is how an IDOR gets in.
    """
    row = storage.get_job(job_id)
    if row is None or row.get("owner_id") != hr.id:
        raise JobNotActive("That job could not be found.")
    return row


@router.post("/jobs", response_model=JobDetail)
async def create_job(payload: JobCreate, hr: HRUser = Depends(require_hr)) -> JobDetail:
    # Save before generating. If generation fails the job still exists and
    # HR is told their description is saved, rather than losing it.
    row = storage.create_job(
        title=payload.title,
        description=payload.description,
        skills=payload.skills,
        experience=payload.experience,
        owner_id=hr.id,
        facts=_job_facts_columns(payload),
    )

    try:
        rubric = _generate_rubric(
            payload.title, payload.description, payload.skills, payload.experience
        )
    except Exception:
        logger.exception("rubric generation failed for job %s", row["id"])
        raise RubricGenerationFailed() from None

    updated = storage.set_job_rubric(row["id"], rubric)
    return _to_detail(updated)


def _parse_job_facts(text: str) -> JobFacts | None:
    """Pull structured facts out of a job description, or give up quietly.

    Failure is not an error here. The raw text is useful on its own, and
    it is exactly what this endpoint returned before parsing existed, so a
    model that is rate limited or returns something unusable degrades to
    the old behavior instead of blocking HR from posting a role.
    """
    system, user = job_facts_prompts(text)
    try:
        return generate_structured(system, user, JobFacts, validate=validate_job_facts)
    except Exception:
        logger.warning("job description parsing failed, returning raw text", exc_info=True)
        return None


@router.post("/jobs/description-document", response_model=JobDescriptionDocument)
async def extract_job_description(
    document: UploadFile = File(...),
    hr: HRUser = Depends(require_hr),
) -> JobDescriptionDocument:
    """Extract a PDF into the HR-editable form.

    HR always reviews and edits what comes back before the job is created.
    The document is an input aid, never an opaque source of truth, which
    is also why nothing here is persisted.
    """
    filename = (document.filename or "").lower()
    if document.content_type != "application/pdf" and not filename.endswith(".pdf"):
        raise JobDescriptionWrongFormat()
    text = _job_document_text(await document.read())
    return JobDescriptionDocument(text=text, facts=_parse_job_facts(text))


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(hr: HRUser = Depends(require_hr)) -> list[JobSummary]:
    rows = storage.list_jobs(owner_id=hr.id)
    counts = storage.pipeline_counts([row["id"] for row in rows])
    return [
        JobSummary(
            id=row["id"],
            title=row["title"],
            state=row["state"],
            created_at=row["created_at"],
            applicant_count=counts[row["id"]]["applicant"],
            shortlisted_count=counts[row["id"]]["shortlisted"],
            interviewed_count=counts[row["id"]]["interviewed"],
        )
        for row in rows
    ]


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, hr: HRUser = Depends(require_hr)) -> JobDetail:
    row = owned_job_or_404(job_id, hr)
    counts = storage.pipeline_counts([job_id])[job_id]
    return _to_detail(row, counts)


@router.post("/jobs/{job_id}/rubric/regenerate", response_model=JobDetail)
async def regenerate_rubric(job_id: str, hr: HRUser = Depends(require_hr)) -> JobDetail:
    row = owned_job_or_404(job_id, hr)

    try:
        rubric = _generate_rubric(
            row["title"], row["description"], row.get("skills") or [], row.get("experience")
        )
    except Exception:
        logger.exception("rubric regeneration failed for job %s", job_id)
        raise RubricGenerationFailed() from None

    updated = storage.set_job_rubric(job_id, rubric)
    counts = storage.pipeline_counts([job_id])[job_id]
    return _to_detail(updated, counts)


@router.get("/apply/{job_id}", response_model=PublicJobSummary)
async def public_job_summary(job_id: str, email: str | None = None) -> PublicJobSummary:
    """Public role detail. The rubric remains private to the hiring team.

    `email` is optional so a shared role link still opens for a stranger.
    Supplied, it tells the page whether this person has already applied, so
    it can offer their application instead of a second one.
    """
    row = storage.get_job(job_id)
    if row is None:
        raise JobNotActive("That job could not be found.")
    if row["state"] != "active":
        raise JobNotActive()
    return _to_public(row, applied=job_id in _applied_job_ids(email))


@router.get("/apply", response_model=list[PublicJobSummary])
async def list_public_jobs(email: str | None = None) -> list[PublicJobSummary]:
    """Roles a candidate may browse and apply to without an invitation URL.

    Every active role is returned, each flagged with whether this address
    has already applied. The filtering is left to the caller on purpose:
    "roles you have applied to" and "roles still open to you" are two views
    of one list, and returning the whole list keeps them consistent with
    each other without a second request.
    """
    applied = _applied_job_ids(email)
    return [
        _to_public(row, applied=row["id"] in applied)
        for row in storage.list_jobs()
        if row["state"] == "active"
    ]

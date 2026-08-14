"""Job routes. backend.md section 4.

Rubric generation runs synchronously inside POST /jobs. It takes 3 to 8
seconds and the request holds open for it, which is correct at this scale
and removes an entire category of failure (backend.md section 1). The
frontend shows "Analyzing job description" for the duration - a single
real state, not fake sub-steps (screens.md section 2 stage B).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.core.errors import JobNotActive, RubricGenerationFailed
from app.core.heuristics import RUBRIC_GENERATION_MAX_RETRIES
from app.integrations import storage
from app.integrations.llm import generate_structured
from app.models import (
    JobCreate,
    JobDetail,
    JobSummary,
    PublicJobSummary,
    Rubric,
)
from app.services.prompts import rubric_prompts
from app.services.validation import validate_rubric

logger = logging.getLogger("rubric.api.jobs")

router = APIRouter(tags=["jobs"])


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
        applicant_count=counts["applicant"],
        shortlisted_count=counts["shortlisted"],
        interviewed_count=counts["interviewed"],
    )


@router.post("/jobs", response_model=JobDetail)
async def create_job(payload: JobCreate) -> JobDetail:
    # Save before generating. If generation fails the job still exists and
    # HR is told their description is saved, rather than losing it.
    row = storage.create_job(
        title=payload.title,
        description=payload.description,
        skills=payload.skills,
        experience=payload.experience,
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


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs() -> list[JobSummary]:
    rows = storage.list_jobs()
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
async def get_job(job_id: str) -> JobDetail:
    row = storage.get_job(job_id)
    if row is None:
        raise JobNotActive("That job could not be found.")
    counts = storage.pipeline_counts([job_id])[job_id]
    return _to_detail(row, counts)


@router.post("/jobs/{job_id}/rubric/regenerate", response_model=JobDetail)
async def regenerate_rubric(job_id: str) -> JobDetail:
    row = storage.get_job(job_id)
    if row is None:
        raise JobNotActive("That job could not be found.")

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
async def public_job_summary(job_id: str) -> PublicJobSummary:
    """Unauthenticated. Title only - never the rubric, which would tell a
    candidate exactly what to say (backend.md section 4)."""
    row = storage.get_job(job_id)
    if row is None:
        raise JobNotActive("That job could not be found.")
    if row["state"] != "active":
        raise JobNotActive()
    return PublicJobSummary(id=row["id"], title=row["title"], state=row["state"])

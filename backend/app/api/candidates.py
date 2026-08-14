"""Candidate routes for HR. backend.md section 4.

The ranked list and the detail view. Approve and reject arrive in Phase 4
alongside interview token minting.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.core.errors import CandidateNotFound, JobNotActive, ScreeningFailed
from app.integrations import storage
from app.models import (
    ApprovalResult,
    CandidateDetail,
    CandidateSummary,
    EvidenceOut,
    Rubric,
    SubScoreOut,
)
from app.services.interview import new_token
from app.services.scoring import band_for
from app.services.screening import screen_candidate

logger = logging.getLogger("rubric.api.candidates")

router = APIRouter(tags=["candidates"])


def _summary(row: dict, skills_total: int) -> CandidateSummary:
    return CandidateSummary(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        screening_score=row.get("screening_score"),
        screening_band=row.get("screening_band"),
        recommendation=row.get("recommendation"),
        matched_count=len(row.get("matched_skills") or []),
        skills_total=skills_total,
        state=row["state"],
        created_at=row["created_at"],
    )


def _sub_scores_out(row: dict, rubric: Rubric | None) -> list[SubScoreOut]:
    """Join stored sub-scores to their rubric names.

    Done here rather than in the browser so the frontend never has to
    reconcile a score against a rubric it fetched separately.
    """
    out: list[SubScoreOut] = []
    for entry in row.get("sub_scores") or []:
        criterion_id = entry.get("criterion_id", "")
        criterion = rubric.by_id(criterion_id) if rubric else None
        out.append(
            SubScoreOut(
                criterion_id=criterion_id,
                criterion_name=criterion.name if criterion else criterion_id,
                points_awarded=entry.get("points_awarded", 0),
                points_possible=entry.get("points_possible", 0),
                evidence=[
                    EvidenceOut(source=e.get("source", ""), quote=e.get("quote", ""))
                    for e in entry.get("evidence") or []
                ],
            )
        )
    return out


@router.get("/jobs/{job_id}/candidates", response_model=list[CandidateSummary])
async def list_candidates(job_id: str) -> list[CandidateSummary]:
    job = storage.get_job(job_id)
    if job is None:
        raise JobNotActive("That job could not be found.")
    skills_total = len(job.get("skills") or [])
    return [_summary(row, skills_total) for row in storage.list_candidates(job_id)]


@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
async def get_candidate(candidate_id: str) -> CandidateDetail:
    row = storage.get_candidate(candidate_id)
    if row is None:
        raise CandidateNotFound()

    job = storage.get_job(row["job_id"])
    rubric = (
        Rubric.model_validate(job["rubric"]) if job and job.get("rubric") else None
    )

    return CandidateDetail(
        id=row["id"],
        job_id=row["job_id"],
        job_title=job["title"] if job else "",
        name=row["name"],
        email=row["email"],
        state=row["state"],
        created_at=row["created_at"],
        screening_score=row.get("screening_score"),
        screening_band=row.get("screening_band"),
        recommendation=row.get("recommendation"),
        sub_scores=_sub_scores_out(row, rubric),
        matched_skills=row.get("matched_skills") or [],
        unevidenced_skills=row.get("unevidenced_skills") or [],
        resume_intro_conflicts=row.get("resume_intro_conflicts") or [],
        assessment=row.get("assessment"),
        transcript=row.get("transcript"),
        # Paths are stored; URLs are minted per response and expire.
        audio_url=storage.signed_url(
            storage.BUCKET_INTRODUCTIONS, row.get("audio_path")
        ),
        resume_url=storage.signed_url(storage.BUCKET_RESUMES, row.get("resume_path")),
        resume_text=row.get("resume_text"),
    )


@router.post("/candidates/{candidate_id}/approve", response_model=ApprovalResult)
async def approve_candidate(candidate_id: str) -> ApprovalResult:
    """Approve for interview and mint the interview link.

    Idempotent: approving twice returns the same token rather than
    creating a second interview or invalidating a link HR may have already
    sent to the candidate.
    """
    row = storage.get_candidate(candidate_id)
    if row is None:
        raise CandidateNotFound()

    existing = storage.get_interview_by_candidate(candidate_id)
    if existing is not None:
        token = existing["token"]
    else:
        token = new_token()
        storage.create_interview(candidate_id, token)

    if row["state"] not in ("approved", "interviewing", "interviewed"):
        storage.set_candidate_state(candidate_id, "approved")

    return ApprovalResult(
        candidate_id=candidate_id,
        state="approved",
        interview_token=token,
        interview_path=f"/interview/{token}",
    )


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateSummary)
async def reject_candidate(candidate_id: str) -> CandidateSummary:
    row = storage.get_candidate(candidate_id)
    if row is None:
        raise CandidateNotFound()

    updated = storage.set_candidate_state(candidate_id, "rejected")
    job = storage.get_job(row["job_id"])
    return _summary(updated, len((job or {}).get("skills") or []))


@router.post("/candidates/{candidate_id}/rescreen", response_model=CandidateDetail)
async def rescreen_candidate(candidate_id: str) -> CandidateDetail:
    """Retry a screening that failed, without asking the candidate to
    reapply. Their audio, transcript and resume are already saved."""
    row = storage.get_candidate(candidate_id)
    if row is None:
        raise CandidateNotFound()

    job = storage.get_job(row["job_id"])
    if job is None or not job.get("rubric"):
        raise JobNotActive("That job no longer has a rubric to score against.")

    rubric = Rubric.model_validate(job["rubric"])

    try:
        result = screen_candidate(
            rubric,
            row.get("transcript") or "",
            row.get("resume_text") or "",
            job.get("skills") or [],
        )
    except Exception:
        logger.exception("rescreen failed for candidate %s", candidate_id)
        raise ScreeningFailed() from None

    storage.save_screening(
        candidate_id,
        score=result.total_score,
        band=band_for(result.total_score),
        sub_scores=[s.model_dump() for s in result.sub_scores],
        matched_skills=result.matched_skills,
        unevidenced_skills=result.unevidenced_skills,
        conflicts=result.resume_intro_conflicts,
        assessment=result.assessment,
        recommendation=result.recommendation,
    )
    return await get_candidate(candidate_id)

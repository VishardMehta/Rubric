"""Candidate routes for HR. backend.md section 4.

The ranked list and the detail view. Approve and reject arrive in Phase 4
alongside interview token minting.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.core.auth import HRUser, require_hr
from app.core.errors import CandidateNotFound, JobNotActive, ScreeningFailed
from app.integrations import storage
from app.models import (
    ApprovalResult,
    CandidateDetail,
    CandidateSummary,
    EvidenceOut,
    ResumeProfile,
    Rubric,
    SubScoreOut,
)
from app.services.interview import new_token
from app.services.resume_profile import build_resume_profile
from app.services.scoring import band_for, weighted_screening
from app.services.screening import screen_candidate

logger = logging.getLogger("rubric.api.candidates")

router = APIRouter(tags=["candidates"])


def _summary(
    row: dict,
    skills_total: int,
    interview: dict | None = None,
    job_title: str | None = None,
) -> CandidateSummary:
    interview = interview or {}
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
        interview_status=interview.get("status"),
        interview_score=interview.get("overall_score"),
        interview_band=interview.get("band"),
        job_id=row.get("job_id"),
        job_title=job_title,
    )


def _sub_scores_out(
    row: dict, rubric: Rubric | None, column: str = "sub_scores"
) -> list[SubScoreOut]:
    """Join stored sub-scores to their rubric names.

    Done here rather than in the browser so the frontend never has to
    reconcile a score against a rubric it fetched separately.

    `column` selects which component: `sub_scores` is the resume scoring,
    `voice_sub_scores` the introduction scoring. Same shape, same rubric,
    different source.
    """
    out: list[SubScoreOut] = []
    for entry in row.get(column) or []:
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


def _resume_profile_out(row: dict) -> ResumeProfile | None:
    """Parse the stored profile, tolerating a stale shape.

    A row written before a field was added, or by an older prompt, should
    show what it can rather than 500 the whole screen. The profile is
    display-only, so a partial one is still useful and a missing one is
    already a supported state.
    """
    raw = row.get("resume_profile")
    if not raw:
        return None
    try:
        return ResumeProfile.model_validate(raw)
    except ValidationError:
        logger.warning("stored resume_profile did not validate for candidate %s", row.get("id"))
        return None


def owned_candidate_or_404(candidate_id: str, hr: HRUser) -> tuple[dict, dict]:
    """Fetch a candidate whose job the signed-in account owns.

    Returns (candidate_row, job_row). This is the gate that matters most in
    the whole API: a candidate row carries the transcript, the resume text
    and signed URLs to the original audio and PDF. Without the owner check
    any signed-in account could read every applicant in the database by
    walking candidate ids.

    Ownership lives on the job, not the candidate, so it always takes two
    reads: candidate, then its job. Every candidate-scoped HR route calls
    this and none of them touch storage.get_candidate directly.
    """
    row = storage.get_candidate(candidate_id)
    if row is None:
        raise CandidateNotFound()
    job = storage.get_job(row["job_id"])
    if job is None or job.get("owner_id") != hr.id:
        # Same 404 as a genuinely missing candidate, so this cannot be used
        # to discover which ids exist under other accounts.
        raise CandidateNotFound()
    return row, job


@router.get("/jobs/{job_id}/candidates", response_model=list[CandidateSummary])
async def list_candidates(
    job_id: str, hr: HRUser = Depends(require_hr)
) -> list[CandidateSummary]:
    job = storage.get_job(job_id)
    if job is None or job.get("owner_id") != hr.id:
        raise JobNotActive("That job could not be found.")
    skills_total = len(job.get("skills") or [])
    rows = storage.list_candidates(job_id)
    # Fetched for the whole page rather than per row: Job Detail groups by
    # pipeline stage and shows interview scores at the top, and an N+1 here
    # would be one round trip per applicant.
    interviews = storage.interview_summaries([row["id"] for row in rows])
    return [
        _summary(row, skills_total, interviews.get(row["id"]), job.get("title"))
        for row in rows
    ]


@router.get("/candidates", response_model=list[CandidateSummary])
async def list_all_candidates(
    hr: HRUser = Depends(require_hr),
) -> list[CandidateSummary]:
    """Every applicant across the signed-in account's roles.

    The cross-role directory used to build this in the browser: list the
    jobs, then one request per job, each of which ran four queries of its
    own. Six roles meant seven requests and around twenty-five queries to
    paint one table. This is three queries and one request.

    Owner scoping is the same rule as everywhere else, applied once at the
    top: the job ids come from `list_jobs(owner_id)`, so a candidate whose
    job this account does not own is never in the set to begin with.
    """
    jobs = storage.list_jobs(owner_id=hr.id)
    if not jobs:
        return []

    skills_total = {job["id"]: len(job.get("skills") or []) for job in jobs}
    titles = {job["id"]: job.get("title") for job in jobs}

    rows = storage.list_candidates_for_jobs(list(skills_total))
    interviews = storage.interview_summaries([row["id"] for row in rows])
    return [
        _summary(
            row,
            skills_total.get(row["job_id"], 0),
            interviews.get(row["id"]),
            titles.get(row["job_id"]),
        )
        for row in rows
    ]


@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
async def get_candidate(
    candidate_id: str, hr: HRUser = Depends(require_hr)
) -> CandidateDetail:
    row, job = owned_candidate_or_404(candidate_id, hr)
    rubric = (
        Rubric.model_validate(job["rubric"]) if job and job.get("rubric") else None
    )

    # The interview, if one has been minted. Candidate Detail needs both of
    # these: the token to show the interview link after approval, and the
    # status to decide whether to offer a link to the result
    # (screens.md section 4, "Post-approval state" and "Interviewed state").
    interview = storage.get_interview_by_candidate(candidate_id)

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
        resume_score=row.get("resume_score"),
        voice_score=row.get("voice_score"),
        sub_scores=_sub_scores_out(row, rubric),
        voice_sub_scores=_sub_scores_out(row, rubric, "voice_sub_scores"),
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
        resume_profile=_resume_profile_out(row),
        interview_status=interview["status"] if interview else None,
        interview_token=interview["token"] if interview else None,
    )


@router.post("/candidates/{candidate_id}/approve", response_model=ApprovalResult)
async def approve_candidate(
    candidate_id: str, hr: HRUser = Depends(require_hr)
) -> ApprovalResult:
    """Approve for interview and mint the interview link.

    Idempotent: approving twice returns the same token rather than
    creating a second interview or invalidating a link HR may have already
    sent to the candidate.

    The read, the insert and the state change happen inside one Postgres
    function rather than as three calls from here. Two fast clicks used to
    interleave: both saw no interview, both inserted, and the loser hit the
    interviews.candidate_id unique constraint and surfaced as a 500.
    """
    owned_candidate_or_404(candidate_id, hr)

    result = storage.approve_candidate_atomic(candidate_id, new_token())

    # Approving and sending are one act in the UI, so the invitation is
    # stamped here. The column exists separately because the candidate
    # portal must only surface a link that was actually sent, and a token
    # minted is not a token sent.
    interview = storage.get_interview_by_candidate(candidate_id)
    if interview and not interview.get("invited_at"):
        storage.mark_interview_invited(interview["id"])

    return ApprovalResult(
        candidate_id=candidate_id,
        state=result["state"],
        interview_token=result["token"],
        interview_path=f"/interview/{result['token']}",
    )


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateSummary)
async def reject_candidate(
    candidate_id: str, hr: HRUser = Depends(require_hr)
) -> CandidateSummary:
    _row, job = owned_candidate_or_404(candidate_id, hr)
    updated = storage.set_candidate_state(candidate_id, "rejected")
    return _summary(updated, len((job or {}).get("skills") or []))


@router.post("/candidates/{candidate_id}/rescreen", response_model=CandidateDetail)
async def rescreen_candidate(
    candidate_id: str, hr: HRUser = Depends(require_hr)
) -> CandidateDetail:
    """Retry a screening that failed, without asking the candidate to
    reapply. Their audio, transcript and resume are already saved."""
    row, job = owned_candidate_or_404(candidate_id, hr)

    if not job.get("rubric"):
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

    # Same weighting as the original screening, from the one function that
    # knows it. A rescreen that scored differently from a first screen
    # would make two candidates on the same job incomparable.
    final_score = weighted_screening(result.total_score, result.voice_total_score)
    storage.save_screening(
        candidate_id,
        score=final_score,
        band=band_for(final_score),
        resume_score=result.total_score,
        voice_score=result.voice_total_score,
        sub_scores=[s.model_dump() for s in result.sub_scores],
        voice_sub_scores=[s.model_dump() for s in result.voice_sub_scores],
        matched_skills=result.matched_skills,
        unevidenced_skills=result.unevidenced_skills,
        conflicts=result.resume_intro_conflicts,
        assessment=result.assessment,
        recommendation=result.recommendation,
    )
    return await get_candidate(candidate_id, hr)


@router.post("/candidates/{candidate_id}/reparse-resume", response_model=CandidateDetail)
async def reparse_resume(
    candidate_id: str, hr: HRUser = Depends(require_hr)
) -> CandidateDetail:
    """Retry a resume profile that failed, without asking the candidate to
    reapply. Mirrors rescreen: their resume text is already saved.

    Unlike rescreen this cannot change any score, because the profile is
    display only and screening reads the raw text.
    """
    row, _job = owned_candidate_or_404(candidate_id, hr)

    resume_text = row.get("resume_text") or ""
    if not resume_text.strip():
        raise CandidateNotFound("There is no resume text to read for this candidate.")

    try:
        profile = build_resume_profile(resume_text)
    except Exception:
        logger.exception("resume reparse failed for candidate %s", candidate_id)
        raise ScreeningFailed(
            "The resume could not be read into a profile. Their resume text is saved."
        ) from None

    storage.save_resume_profile(candidate_id, profile.model_dump())
    return await get_candidate(candidate_id, hr)

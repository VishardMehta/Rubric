"""Supabase access. The only place that talks to the database.

Uses the service_role key and bypasses row level security, per CLAUDE.md.
The frontend holds no Supabase credential at all, so this module is the
single place access has to be reasoned about.

Object paths, never URLs, are stored in the database. URLs expire; paths do
not. signed_url() resolves a path at response time.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.core.config import get_settings
from app.core.errors import AlreadyApplied, RubricError
from app.models import Rubric

logger = logging.getLogger("rubric.storage")

BUCKET_INTRODUCTIONS = "introductions"
BUCKET_ANSWERS = "answers"
BUCKET_RESUMES = "resumes"

SIGNED_URL_TTL_SECONDS = 60 * 60  # one hour, ample for one page view


class StorageNotConfigured(RubricError):
    code = "storage_not_configured"
    status_code = 503
    retryable = False
    default_message = (
        "The database is not configured. Set SUPABASE_URL and "
        "SUPABASE_SERVICE_ROLE_KEY in backend/.env."
    )


@lru_cache
def get_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise StorageNotConfigured()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# ---------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------


def create_job(
    title: str,
    description: str,
    skills: list[str],
    experience: str | None,
) -> dict[str, Any]:
    """Insert the job before generating its rubric.

    Saving first is deliberate: if rubric generation fails, the job still
    exists and HR sees "your job description is saved, try again" rather
    than losing what they typed (screens.md section 2 error state).
    """
    response = (
        get_client()
        .table("jobs")
        .insert(
            {
                "title": title,
                "description": description,
                "skills": skills,
                "experience": experience,
                "state": "analyzing",
            }
        )
        .execute()
    )
    return response.data[0]


def set_job_rubric(job_id: str, rubric: Rubric) -> dict[str, Any]:
    """Attach the generated rubric and open the job for applications."""
    response = (
        get_client()
        .table("jobs")
        .update({"rubric": rubric.model_dump(), "state": "active"})
        .eq("id", job_id)
        .execute()
    )
    return response.data[0]


def get_job(job_id: str) -> dict[str, Any] | None:
    response = get_client().table("jobs").select("*").eq("id", job_id).execute()
    return response.data[0] if response.data else None


def list_jobs() -> list[dict[str, Any]]:
    response = (
        get_client()
        .table("jobs")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def delete_job(job_id: str) -> None:
    get_client().table("jobs").delete().eq("id", job_id).execute()


# ---------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------


def create_candidate(
    job_id: str,
    name: str,
    email: str,
    resume_path: str | None,
    resume_text: str | None,
    audio_path: str | None,
    transcript: str | None,
) -> dict[str, Any]:
    """Insert the applicant before screening runs.

    Saved first for the same reason jobs are: if screening fails, the
    candidate still exists with their audio and transcript intact, and HR
    can retry from the dashboard rather than asking them to reapply.
    """
    try:
        response = (
            get_client()
            .table("candidates")
            .insert(
                {
                    "job_id": job_id,
                    "name": name,
                    "email": email,
                    "resume_path": resume_path,
                    "resume_text": resume_text,
                    "audio_path": audio_path,
                    "transcript": transcript,
                    "state": "screening",
                }
            )
            .execute()
        )
    except Exception as exc:
        if _is_unique_violation(exc):
            raise AlreadyApplied() from exc
        raise
    return response.data[0]


def _is_unique_violation(exc: Exception) -> bool:
    """Detect the (job_id, email) unique constraint.

    supabase-py surfaces PostgREST errors as a generic exception, so the
    Postgres error code is matched in the message. 23505 is
    unique_violation.
    """
    text = str(exc)
    return "23505" in text or "candidates_one_application_per_job" in text


def save_screening(
    candidate_id: str,
    *,
    score: int,
    band: str,
    sub_scores: list[dict[str, Any]],
    matched_skills: list[str],
    unevidenced_skills: list[str],
    conflicts: list[str],
    assessment: str,
    recommendation: str,
) -> dict[str, Any]:
    response = (
        get_client()
        .table("candidates")
        .update(
            {
                "screening_score": score,
                "screening_band": band,
                "sub_scores": sub_scores,
                "matched_skills": matched_skills,
                "unevidenced_skills": unevidenced_skills,
                "resume_intro_conflicts": conflicts,
                "assessment": assessment,
                "recommendation": recommendation,
                "state": "screened",
            }
        )
        .eq("id", candidate_id)
        .execute()
    )
    return response.data[0]


def mark_screening_failed(candidate_id: str) -> None:
    """Roll the candidate back to `applied` so HR sees a retryable state
    rather than one stuck mid-screening forever."""
    get_client().table("candidates").update({"state": "applied"}).eq(
        "id", candidate_id
    ).execute()


def get_candidate(candidate_id: str) -> dict[str, Any] | None:
    response = (
        get_client().table("candidates").select("*").eq("id", candidate_id).execute()
    )
    return response.data[0] if response.data else None


def list_candidates(job_id: str) -> list[dict[str, Any]]:
    """Ranked by score, highest first. Candidates still being screened
    have a null score and sort last."""
    response = (
        get_client()
        .table("candidates")
        .select("*")
        .eq("job_id", job_id)
        .order("screening_score", desc=True, nullsfirst=False)
        .execute()
    )
    return response.data or []


def set_candidate_state(candidate_id: str, state: str) -> dict[str, Any]:
    response = (
        get_client()
        .table("candidates")
        .update({"state": state})
        .eq("id", candidate_id)
        .execute()
    )
    return response.data[0]


# ---------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------


def create_interview(candidate_id: str, token: str) -> dict[str, Any]:
    response = (
        get_client()
        .table("interviews")
        .insert({"candidate_id": candidate_id, "token": token})
        .execute()
    )
    return response.data[0]


def get_interview_by_token(token: str) -> dict[str, Any] | None:
    response = (
        get_client().table("interviews").select("*").eq("token", token).execute()
    )
    return response.data[0] if response.data else None


def get_interview_by_candidate(candidate_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("interviews")
        .select("*")
        .eq("candidate_id", candidate_id)
        .execute()
    )
    return response.data[0] if response.data else None


def start_interview(
    interview_id: str, plan: dict[str, Any], total_questions: int, state: dict[str, Any]
) -> dict[str, Any]:
    response = (
        get_client()
        .table("interviews")
        .update(
            {
                "plan": plan,
                "total_questions": total_questions,
                "state_object": state,
                "status": "in_progress",
                "started_at": "now()",
            }
        )
        .eq("id", interview_id)
        .execute()
    )
    return response.data[0]


def update_interview_state(interview_id: str, state: dict[str, Any]) -> None:
    get_client().table("interviews").update({"state_object": state}).eq(
        "id", interview_id
    ).execute()


def complete_interview(interview_id: str, state: dict[str, Any]) -> None:
    get_client().table("interviews").update(
        {"state_object": state, "status": "complete", "completed_at": "now()"}
    ).eq("id", interview_id).execute()


def mark_interview_evaluated(interview_id: str) -> None:
    get_client().table("interviews").update({"status": "evaluated"}).eq(
        "id", interview_id
    ).execute()


# ---------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------


def create_turn(
    interview_id: str, slot: int, question: str, criterion_ids: list[str]
) -> dict[str, Any]:
    response = (
        get_client()
        .table("interview_turns")
        .insert(
            {
                "interview_id": interview_id,
                "slot": slot,
                "question": question,
                "criterion_ids": criterion_ids,
            }
        )
        .execute()
    )
    return response.data[0]


def save_answer(
    interview_id: str,
    slot: int,
    answer_text: str,
    answer_audio_path: str | None,
    answer_scores: list[dict[str, Any]],
    response_time_seconds: int | None,
) -> dict[str, Any]:
    response = (
        get_client()
        .table("interview_turns")
        .update(
            {
                "answer_text": answer_text,
                "answer_audio_path": answer_audio_path,
                "answer_scores": answer_scores,
                "response_time_seconds": response_time_seconds,
                "answered_at": "now()",
            }
        )
        .eq("interview_id", interview_id)
        .eq("slot", slot)
        .execute()
    )
    return response.data[0]


def list_turns(interview_id: str) -> list[dict[str, Any]]:
    response = (
        get_client()
        .table("interview_turns")
        .select("*")
        .eq("interview_id", interview_id)
        .order("slot")
        .execute()
    )
    return response.data or []


# ---------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------


def save_interview_result(
    interview_id: str,
    *,
    overall: int,
    technical: int,
    communication: int,
    experience: int,
    band: str,
    strengths: list[str],
    concerns: list[str],
    recommendation: str,
) -> dict[str, Any]:
    response = (
        get_client()
        .table("interview_results")
        .upsert(
            {
                "interview_id": interview_id,
                "overall_score": overall,
                "technical_score": technical,
                "communication_score": communication,
                "experience_score": experience,
                "band": band,
                "strengths": strengths,
                "concerns": concerns,
                "recommendation": recommendation,
            }
        )
        .execute()
    )
    return response.data[0]


def get_interview_result(interview_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("interview_results")
        .select("*")
        .eq("interview_id", interview_id)
        .execute()
    )
    return response.data[0] if response.data else None


# ---------------------------------------------------------------------
# Pipeline counts
# ---------------------------------------------------------------------


def pipeline_counts(job_ids: list[str]) -> dict[str, dict[str, int]]:
    """Applicant, shortlisted and interviewed counts per job.

    One query for every job on the page rather than one query per job. At
    demo scale the row count is small enough that counting in Python is
    both simpler and faster than three aggregate round trips.
    """
    counts = {job_id: {"applicant": 0, "shortlisted": 0, "interviewed": 0} for job_id in job_ids}
    if not job_ids:
        return counts

    response = (
        get_client()
        .table("candidates")
        .select("job_id, recommendation, state")
        .in_("job_id", job_ids)
        .execute()
    )

    for row in response.data or []:
        bucket = counts.get(row["job_id"])
        if bucket is None:
            continue
        bucket["applicant"] += 1
        if row.get("recommendation") == "shortlist":
            bucket["shortlisted"] += 1
        if row.get("state") == "interviewed":
            bucket["interviewed"] += 1

    return counts


# ---------------------------------------------------------------------
# Object storage
# ---------------------------------------------------------------------


def upload(bucket: str, path: str, data: bytes, content_type: str) -> str:
    """Upload and return the object path. Never returns a URL - see the
    module docstring."""
    get_client().storage.from_(bucket).upload(
        path=path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return path


def signed_url(bucket: str, path: str | None) -> str | None:
    """Resolve a stored object path to a time limited URL."""
    if not path:
        return None
    try:
        response = get_client().storage.from_(bucket).create_signed_url(
            path, SIGNED_URL_TTL_SECONDS
        )
        return response.get("signedURL") or response.get("signedUrl")
    except Exception as exc:  # noqa: BLE001 - a missing object must not 500 the page
        logger.warning("could not sign %s/%s: %r", bucket, path, exc)
        return None

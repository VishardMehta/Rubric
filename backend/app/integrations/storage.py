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
from app.core.errors import AlreadyApplied, EmailAlreadyRegistered, RubricError
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

    # DEMO_MODE swaps the client, not the functions above it. Every query,
    # filter, ordering rule and unique-constraint check in this module then
    # runs for real against an in-memory store seeded from the recorded
    # golden rows - see demo_supabase.py for why that seam was chosen.
    if settings.demo_mode:
        from app import cassettes
        from app.integrations.demo_supabase import DemoClient

        logger.warning("DEMO_MODE: using the in-memory store, not Supabase")
        return DemoClient(cassettes.supabase_seed())  # type: ignore[return-value]

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise StorageNotConfigured()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# ---------------------------------------------------------------------
# HR accounts
# ---------------------------------------------------------------------


def create_hr_user(
    email: str,
    name: str,
    company: str | None,
    password_hash: str,
    password_salt: str,
) -> dict[str, Any]:
    """Register an account, claiming any ownerless jobs if it is the first.

    Goes through the `register_hr_user` Postgres function rather than a
    plain insert, because the insert and the claim have to be one
    transaction. See database/002_accounts.sql for why.
    """
    try:
        response = get_client().rpc(
            "register_hr_user",
            {
                "p_email": email,
                "p_name": name,
                "p_company": company,
                "p_password_hash": password_hash,
                "p_password_salt": password_salt,
            },
        ).execute()
    except Exception as exc:
        if _is_unique_violation(exc):
            raise EmailAlreadyRegistered() from exc
        raise
    return response.data


def get_hr_user_by_email(email: str) -> dict[str, Any] | None:
    response = get_client().table("hr_users").select("*").eq("email", email).execute()
    return response.data[0] if response.data else None


def get_hr_user(hr_user_id: str) -> dict[str, Any] | None:
    response = get_client().table("hr_users").select("*").eq("id", hr_user_id).execute()
    return response.data[0] if response.data else None


def create_session(token: str, hr_user_id: str, expires_at: str) -> dict[str, Any]:
    response = (
        get_client()
        .table("hr_sessions")
        .insert({"token": token, "hr_user_id": hr_user_id, "expires_at": expires_at})
        .execute()
    )
    return response.data[0]


def get_session(token: str) -> dict[str, Any] | None:
    """The session row, or None. Expiry is checked by the caller so that an
    expired session can be deleted rather than just ignored."""
    response = get_client().table("hr_sessions").select("*").eq("token", token).execute()
    return response.data[0] if response.data else None


def delete_session(token: str) -> None:
    get_client().table("hr_sessions").delete().eq("token", token).execute()


# ---------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------


def create_job(
    title: str,
    description: str,
    skills: list[str],
    experience: str | None,
    owner_id: str,
    facts: dict[str, Any] | None = None,
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
                "owner_id": owner_id,
                # location, department, compensation, employment_type,
                # workplace_type. Optional, and absent rather than null when
                # not supplied so the column defaults still apply.
                **(facts or {}),
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


def list_jobs(owner_id: str | None = None) -> list[dict[str, Any]]:
    """Jobs newest first.

    `owner_id` is required by every HR caller. It stays optional here only
    for the candidate-facing public list, which needs every active job
    regardless of who posted it, and for the recording harness. A caller
    that forgets it on an HR path leaks other accounts' jobs, so the route
    layer never calls this without one.
    """
    query = get_client().table("jobs").select("*")
    if owner_id is not None:
        query = query.eq("owner_id", owner_id)
    return query.order("created_at", desc=True).execute().data or []


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
    resume_profile: dict[str, Any] | None = None,
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
                    "resume_profile": resume_profile,
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
    """Detect a unique-constraint violation.

    Used by the (job_id, email) constraint on candidates and by the email
    constraint on hr_users, which is why the code is matched rather than
    only the candidates constraint name.

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
    resume_score: int,
    voice_score: int,
    sub_scores: list[dict[str, Any]],
    voice_sub_scores: list[dict[str, Any]],
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
                # The weighted result, and the two components behind it.
                # Written together so a row can never carry a total whose
                # parts are missing (database/003_screening_components.sql).
                "screening_score": score,
                "screening_band": band,
                "resume_score": resume_score,
                "voice_score": voice_score,
                "sub_scores": sub_scores,
                "voice_sub_scores": voice_sub_scores,
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


def save_resume_profile(candidate_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Store a structured resume profile. Display only, never a score."""
    response = (
        get_client()
        .table("candidates")
        .update({"resume_profile": profile})
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


# Everything a list row needs, and nothing else.
#
# `select("*")` on this table is expensive in a way that is invisible
# locally: a candidate row carries resume_text, transcript, assessment and
# the sub_scores jsonb, which together run to tens of kilobytes each. A
# list of twenty applicants was pulling most of a megabyte over the wire
# from Supabase to render name, score and state.
#
# Anything added here must be a column `_summary` in api/candidates.py
# actually reads. The demo store ignores projection and returns whole rows,
# so a field missing from this list still works in DEMO_MODE and fails
# against Supabase. That asymmetry is the reason to keep the list tight and
# the reason to keep it in one place.
CANDIDATE_SUMMARY_COLUMNS = (
    "id, job_id, name, email, state, created_at, "
    "screening_score, screening_band, recommendation, matched_skills"
)


def list_candidates(job_id: str) -> list[dict[str, Any]]:
    """Ranked by score, highest first. Candidates still being screened
    have a null score and sort last."""
    response = (
        get_client()
        .table("candidates")
        .select(CANDIDATE_SUMMARY_COLUMNS)
        .eq("job_id", job_id)
        .order("screening_score", desc=True, nullsfirst=False)
        .execute()
    )
    return response.data or []


def list_candidates_for_jobs(job_ids: list[str]) -> list[dict[str, Any]]:
    """Summary rows for several jobs at once, ranked by score.

    The cross-role directory used to fetch one job at a time from the
    browser: with six roles that was six requests, each doing four queries
    of its own. This is one.
    """
    if not job_ids:
        return []
    response = (
        get_client()
        .table("candidates")
        .select(CANDIDATE_SUMMARY_COLUMNS)
        .in_("job_id", job_ids)
        .order("screening_score", desc=True, nullsfirst=False)
        .execute()
    )
    return response.data or []


def interview_summaries(candidate_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Interview status and overall score, keyed by candidate id.

    Two extra queries rather than a PostgREST embedded select. The demo
    store implements only `eq` and `in_` filters and no embeds, so an
    embedded query would work against Supabase and fail in DEMO_MODE, which
    is exactly the drift the demo store exists to prevent. At demo scale
    two round trips cost nothing.
    """
    if not candidate_ids:
        return {}

    interviews = (
        get_client()
        .table("interviews")
        .select("id, candidate_id, status")
        .in_("candidate_id", candidate_ids)
        .execute()
        .data
        or []
    )
    if not interviews:
        return {}

    # Not `*`: an interview_result carries strengths, concerns and the
    # per-dimension breakdown, none of which a list row shows.
    results = (
        get_client()
        .table("interview_results")
        .select("interview_id, overall_score, band")
        .in_("interview_id", [i["id"] for i in interviews])
        .execute()
        .data
        or []
    )
    by_interview = {r["interview_id"]: r for r in results}

    summaries: dict[str, dict[str, Any]] = {}
    for interview in interviews:
        result = by_interview.get(interview["id"]) or {}
        summaries[interview["candidate_id"]] = {
            "status": interview.get("status"),
            "overall_score": result.get("overall_score"),
            "band": result.get("band"),
        }
    return summaries


def job_titles(job_ids: list[str]) -> dict[str, str]:
    """Titles keyed by job id, in one query.

    For screens that list rows from several jobs and need nothing about the
    job but its name. Fetching whole job rows here would pull the rubric
    jsonb and the full description for each one.
    """
    if not job_ids:
        return {}
    response = (
        get_client()
        .table("jobs")
        .select("id, title")
        .in_("id", list(set(job_ids)))
        .execute()
    )
    return {row["id"]: row.get("title") or "" for row in response.data or []}


def invitations_by_candidate(candidate_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Interview status, token and invite time, keyed by candidate id.

    The candidate portal needs all three per application, and used to make
    one round trip per row to get them.
    """
    if not candidate_ids:
        return {}
    response = (
        get_client()
        .table("interviews")
        .select("candidate_id, status, token, invited_at")
        .in_("candidate_id", candidate_ids)
        .execute()
    )
    return {row["candidate_id"]: row for row in response.data or []}


def list_candidates_by_email(email: str) -> list[dict[str, Any]]:
    """Every application from one email address, newest first.

    Used only by the candidate portal, which looks a person up by the
    address they applied with.

    Four columns, and none of them is a score. The route is already written
    field by field from a whitelist so a score cannot reach a candidate;
    projecting here means the score is not even in the process memory that
    builds that response. Belt and braces on the one rule this side of the
    product must not break (product.md section 2).
    """
    response = (
        get_client()
        .table("candidates")
        .select("id, job_id, state, created_at")
        .eq("email", email)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def list_all_candidates() -> list[dict[str, Any]]:
    """Every candidate, newest first.

    Only used by the candidate portal's demo fallback. Not owner scoped,
    which is exactly why it has no other caller, and why it projects the
    same score-free columns as the lookup it stands in for.
    """
    response = (
        get_client()
        .table("candidates")
        .select("id, job_id, state, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def mark_interview_invited(interview_id: str) -> dict[str, Any]:
    """Record that HR sent the interview link.

    Distinct from the interview's created_at, which is when the token was
    minted. Approving and sending are separate acts, and the candidate
    portal only surfaces a link that was actually sent.
    """
    response = (
        get_client()
        .table("interviews")
        .update({"invited_at": "now()"})
        .eq("id", interview_id)
        .execute()
    )
    return response.data[0]


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


def approve_candidate_atomic(candidate_id: str, token: str) -> dict[str, Any]:
    """Mint the interview token and move the candidate to approved, as one
    transaction. Returns {"token", "state"}.

    `token` is the token to use if none exists yet. When the candidate was
    already approved the stored token is returned instead and the one
    passed in is discarded, because HR may already have sent the earlier
    link and replacing it would break a URL that is already in someone's
    inbox. See database/002_accounts.sql.
    """
    response = get_client().rpc(
        "approve_candidate_atomic",
        {"p_candidate_id": candidate_id, "p_token": token},
    ).execute()
    return response.data


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

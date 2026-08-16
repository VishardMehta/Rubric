"""The candidate's own view of their applications.

Unauthenticated and looked up by the email the person applied with, in
keeping with the rest of the candidate side (product.md section 5). There
are no candidate accounts: adding a password here would mean a reset flow,
which would mean email delivery, which is out of scope.

What that trades away, stated plainly rather than left implicit: anyone who
knows an email address can see the list of roles that address applied to,
and the status of each. It carries no score, no band, no recommendation and
no assessment, so the disclosure is "this person applied to these jobs".
For a localhost demo that is acceptable, and it is written down in the
README next to the other stated limits.

**The rule this module exists to hold.** The candidate never sees a score,
at any point, including on completion (product.md section 2). Every
response here is assembled field by field from an explicit whitelist. Never
spread a candidate row into a response model, and never reuse a model that
was designed for HR.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.integrations import storage
from app.models import CandidateApplication
from app.services.accounts import normalise_email

logger = logging.getLogger("rubric.api.applications")

router = APIRouter(tags=["applications"])


# Internal candidate state, and the interview status when there is one,
# mapped to what the applicant is told. The interview states are checked
# first because they are more specific than the candidate state behind
# them.
def _status(candidate_state: str, interview: dict | None) -> tuple[str, str, str]:
    """Return (status, label, detail) for one application."""
    interview_status = (interview or {}).get("status")

    if candidate_state == "rejected":
        # Never "rejected". The candidate is told the outcome, not the
        # judgement, and certainly not the number behind it.
        return (
            "closed",
            "Closed",
            "This role is no longer moving forward with your application.",
        )

    if interview_status in ("complete", "evaluated"):
        return (
            "interview_complete",
            "Interview complete",
            "Your answers have been sent to the hiring team for review.",
        )

    if interview_status == "in_progress":
        return (
            "interview_in_progress",
            "Interview in progress",
            "You can pick up where you left off.",
        )

    if candidate_state in ("approved", "interviewing") and interview is not None:
        return (
            "interview_ready",
            "Interview ready",
            "The hiring team has invited you to a voice interview.",
        )

    if candidate_state in ("screened", "screening", "applied"):
        return (
            "in_review",
            "In review",
            "Your application is with the hiring team.",
        )

    return ("submitted", "Submitted", "Your application has been received.")


@router.get("/applications", response_model=list[CandidateApplication])
async def list_applications(
    email: str = Query(..., min_length=3),
) -> list[CandidateApplication]:
    """Every application submitted with this email, newest first.

    Built field by field on purpose. A candidate row carries
    screening_score, screening_band, recommendation, sub_scores and
    assessment, and none of them may appear in this response.
    """
    normalised = normalise_email(email)
    rows = storage.list_candidates_by_email(normalised)

    # Demo convenience. Typing an address nobody applied with returns an
    # empty list, which during a walkthrough looks like the feature is
    # broken rather than like the address was wrong. With demo_auth on,
    # fall back to every application so the screen has something on it.
    #
    # A real address still returns exactly its own applications, so this
    # only ever widens an answer that was empty. It is still a disclosure,
    # and it is gated behind the same flag as the password bypass.
    if not rows and get_settings().demo_auth:
        logger.warning("DEMO_AUTH: %s has no applications, showing all", normalised)
        rows = storage.list_all_candidates()

    # Three queries for the whole list, not two per row. This screen loads
    # on arrival now that the portal knows who is looking, so the round
    # trips were happening while the candidate watched a spinner.
    titles = storage.job_titles([row["job_id"] for row in rows])
    invitations = storage.invitations_by_candidate([row["id"] for row in rows])

    out: list[CandidateApplication] = []
    for row in rows:
        interview = invitations.get(row["id"])
        status, label, detail = _status(row["state"], interview)

        # The link appears only once HR has actually sent it, and is
        # withdrawn once the interview is over so a finished link cannot be
        # reopened from this screen.
        interview_url = None
        if (
            status in ("interview_ready", "interview_in_progress")
            and interview
            and interview.get("invited_at")
        ):
            interview_url = f"/interview/{interview['token']}"

        out.append(
            CandidateApplication(
                candidate_id=row["id"],
                job_id=row["job_id"],
                job_title=titles.get(row["job_id"]) or "This role",
                applied_at=row["created_at"],
                status=status,
                status_label=label,
                status_detail=detail,
                interview_url=interview_url,
            )
        )
    return out

"""Structure one resume into education, work history, skills and links.

Feeds Candidate Detail so HR can see who they are looking at without
reading a wall of extracted text. It never feeds a score: screening reads
the raw resume text against the rubric and remains the only stage that
produces a number.

Kept out of screening deliberately. Summarising the resume first and then
scoring the summary would put a lossy step between the evidence and the
number, and the evidence quotes on Candidate Detail are checked against
the original text.
"""

from __future__ import annotations

import logging

from app.integrations.llm import generate_structured
from app.models import ResumeProfile
from app.services.prompts import resume_profile_prompts
from app.services.validation import validate_resume_profile

logger = logging.getLogger("rubric.resume_profile")


def build_resume_profile(resume_text: str) -> ResumeProfile:
    """Structure a resume. Raises if the model cannot produce a valid one."""
    system, user = resume_profile_prompts(resume_text)
    return generate_structured(
        system, user, ResumeProfile, validate=validate_resume_profile
    )


def try_build_resume_profile(resume_text: str) -> dict | None:
    """The same, but never raising.

    Called inside the application flow, where this is the least important
    thing happening. A candidate has just recorded a two minute
    introduction; losing their application because a display-only
    convenience failed would be absurd. On failure the column stays null
    and Candidate Detail falls back to the raw resume text it has always
    shown.
    """
    if not resume_text or not resume_text.strip():
        return None
    try:
        return build_resume_profile(resume_text).model_dump()
    except Exception:
        logger.warning("resume profiling failed, continuing without it", exc_info=True)
        return None

"""backend.md section 11: test_image_pdf_rejected."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ResumeNotReadable, ResumeTooLarge, ResumeWrongFormat
from app.core.heuristics import RESUME_MAX_BYTES, RESUME_MIN_READABLE_CHARS
from app.integrations.resume import extract_resume

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_real_text():
    pdf = (FIXTURES / "good_resume.pdf").read_bytes()
    text = extract_resume(pdf)
    assert len(text) >= RESUME_MIN_READABLE_CHARS
    assert "Priya Nair" in text
    assert "cold start problem" in text


def test_image_only_pdf_rejected():
    """A PDF with no content stream behaves like a scanned document for
    extraction purposes: pypdf returns no text, and that must be rejected
    with instructions rather than silently screened as an empty resume."""
    pdf = (FIXTURES / "scanned_resume.pdf").read_bytes()
    with pytest.raises(ResumeNotReadable):
        extract_resume(pdf)


def test_non_pdf_rejected():
    data = (FIXTURES / "not_a_pdf.bin").read_bytes()
    with pytest.raises(ResumeWrongFormat):
        extract_resume(data)


def test_empty_file_rejected():
    with pytest.raises(ResumeWrongFormat):
        extract_resume(b"")


def test_oversized_resume_rejected():
    oversized = b"%PDF-1.4\n" + b"0" * RESUME_MAX_BYTES
    with pytest.raises(ResumeTooLarge):
        extract_resume(oversized)


def test_normalisation_collapses_whitespace_and_strips_lines():
    from app.integrations.resume import _normalise

    messy = "  Priya   Nair  \n\n\n\n   Backend   engineer  \t\twith  gaps  "
    clean = _normalise(messy)
    assert "   " not in clean
    assert "\n\n\n" not in clean
    assert clean.startswith("Priya Nair")


# ---------------------------------------------------------------------
# Resume profile. Structured for display, never for a score.
# ---------------------------------------------------------------------


def test_a_resume_profile_that_fails_does_not_fail_the_application():
    """The candidate has just recorded a two minute introduction. Losing
    that because a display-only convenience failed would be absurd."""
    from unittest.mock import patch

    from app.services.resume_profile import try_build_resume_profile

    with patch(
        "app.services.resume_profile.build_resume_profile",
        side_effect=RuntimeError("provider is unhappy"),
    ):
        assert try_build_resume_profile("Some resume text") is None


def test_an_empty_resume_is_not_sent_to_the_model():
    from app.services.resume_profile import try_build_resume_profile

    assert try_build_resume_profile("") is None
    assert try_build_resume_profile("   ") is None


def test_a_sparse_profile_is_valid():
    """A resume with no dates, no grades and no links is a real resume,
    not a parse failure. Every field is allowed to be absent."""
    from app.models import ResumeProfile
    from app.services.validation import validate_resume_profile

    profile = ResumeProfile(
        headline=None, education=[], experience=[], skills=[], links=[]
    )
    validate_resume_profile(profile)  # does not raise


def test_too_many_skills_is_rejected():
    from app.core.heuristics import RESUME_PROFILE_MAX_SKILLS
    from app.integrations.llm import ValidationViolation
    from app.models import ResumeProfile
    from app.services.validation import validate_resume_profile

    profile = ResumeProfile(
        headline=None,
        education=[],
        experience=[],
        skills=[f"skill{i}" for i in range(RESUME_PROFILE_MAX_SKILLS + 1)],
        links=[],
    )
    with pytest.raises(ValidationViolation):
        validate_resume_profile(profile)


def test_too_many_highlights_on_one_role_is_rejected():
    from app.core.heuristics import RESUME_PROFILE_MAX_HIGHLIGHTS
    from app.integrations.llm import ValidationViolation
    from app.models import ExperienceEntry, ResumeProfile
    from app.services.validation import validate_resume_profile

    profile = ResumeProfile(
        headline=None,
        education=[],
        experience=[
            ExperienceEntry(
                organisation="Unessa Foundation",
                role="Data Science Intern",
                period=None,
                highlights=["a"] * (RESUME_PROFILE_MAX_HIGHLIGHTS + 1),
            )
        ],
        skills=[],
        links=[],
    )
    with pytest.raises(ValidationViolation):
        validate_resume_profile(profile)


def test_a_stored_profile_that_no_longer_validates_does_not_break_the_screen():
    """A row written by an older prompt should show nothing rather than
    500 the whole candidate page."""
    from app.api.candidates import _resume_profile_out

    assert _resume_profile_out({"id": "c1", "resume_profile": {"unexpected": True}}) is None
    assert _resume_profile_out({"id": "c1", "resume_profile": None}) is None
    assert _resume_profile_out({"id": "c1"}) is None


def test_a_link_label_is_not_accepted_as_a_url():
    """Seen on a real resume: a PDF hyperlink whose anchor text is
    "Kaggle" extracts as the bare word, and the model returned that word as
    a link. Rendered as an anchor it would go nowhere."""
    from app.integrations.llm import ValidationViolation
    from app.models import ResumeProfile
    from app.services.validation import validate_resume_profile

    labelled = ResumeProfile(
        headline=None, education=[], experience=[], skills=[], links=["Kaggle"]
    )
    with pytest.raises(ValidationViolation):
        validate_resume_profile(labelled)

    real = ResumeProfile(
        headline=None,
        education=[],
        experience=[],
        skills=[],
        links=["https://github.com/example", "www.example.com/portfolio"],
    )
    validate_resume_profile(real)  # does not raise

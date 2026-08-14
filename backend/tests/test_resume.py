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

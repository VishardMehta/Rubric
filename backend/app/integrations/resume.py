"""Resume PDF text extraction. backend.md section 7.1.

pypdf only - pure Python, MIT, no system dependencies. Deliberately not
pydparser or spaCy: the screening call reads this text directly against the
rubric, which is simpler and better than keyword extraction. See
docs/prior-art.md.
"""

from __future__ import annotations

import io
import logging
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.errors import ResumeNotReadable, ResumeTooLarge, ResumeWrongFormat
from app.core.heuristics import RESUME_MAX_BYTES, RESUME_MAX_CHARS, RESUME_MIN_READABLE_CHARS

logger = logging.getLogger("rubric.resume")

_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _normalise(text: str) -> str:
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()[:RESUME_MAX_CHARS]


def extract_resume(pdf: bytes) -> str:
    """Text from a PDF resume. Raises on anything that is not one.

    Image-only PDFs produce little or no extractable text. Rather than
    silently return an empty string (which would make screening run against
    nothing and blame the candidate for a low score), extraction that yields
    fewer than RESUME_MIN_READABLE_CHARS characters is treated as a scanned
    document and rejected with instructions. No OCR fallback - that is a
    paid service or a heavy local dependency, and the candidate can fix it
    in ten seconds by exporting a text PDF instead.
    """
    if len(pdf) > RESUME_MAX_BYTES:
        raise ResumeTooLarge()
    if len(pdf) == 0:
        raise ResumeWrongFormat("That file is empty. Upload a PDF resume.")

    try:
        reader = PdfReader(io.BytesIO(pdf))
    except PdfReadError as exc:
        raise ResumeWrongFormat() from exc

    if reader.is_encrypted:
        # pypdf can sometimes open a password-protected PDF with an empty
        # user password; try that before giving up.
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ResumeWrongFormat(
                "That PDF is password protected. Upload an unprotected PDF."
            ) from exc

    try:
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        logger.warning("resume text extraction failed: %r", exc)
        raise ResumeWrongFormat() from exc

    text = _normalise(raw_text)

    if len(text) < RESUME_MIN_READABLE_CHARS:
        raise ResumeNotReadable()

    return text

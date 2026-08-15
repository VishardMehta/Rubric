"""The streamed application submission.

`/apply/{job_id}` and `/apply/{job_id}/stream` run the same generator, so
these tests are mostly about the two things streaming adds: that a stage
name reaches the browser *before* the work it describes rather than after,
and that a failure after the response has started still arrives in the one
error shape the frontend knows how to render. Mirrors
test_interview_stream.py.

Storage, resume extraction, transcription and screening are all mocked.
What is under test is the route contract, not the providers.
"""

from __future__ import annotations

import json

import pytest

from app.api import apply as apply_api
from app.core.errors import TranscriptionFailed
from app.models import Evidence, Screening, SubScore
from tests.fixtures.rubrics import valid_rubric

JOB_ID = "job-1"


@pytest.fixture
def wired(monkeypatch):
    """Patch the whole submission so only ordering and shape are exercised.

    `calls` records every side effect in the order it happened, which is how
    the stage-before-work assertions below are made.
    """
    rubric = valid_rubric()
    calls: list[str] = []

    job_row = {
        "id": JOB_ID,
        "title": "Senior Python Developer",
        "state": "active",
        "rubric": rubric.model_dump(),
        "skills": ["Python", "Django"],
    }

    monkeypatch.setattr(apply_api.storage, "get_job", lambda job_id: job_row)

    def fake_extract_resume(data):
        calls.append("extract_resume")
        return "Five years of Python and Django experience."

    def fake_transcribe(data, filename):
        calls.append("transcribe")
        return "Hi, I'm Priya. I built a recommendation service at Zoho."

    def fake_screen_candidate(rubric_, transcript, resume_text, declared_skills):
        calls.append("screen_candidate")
        return Screening(
            sub_scores=[
                SubScore(
                    criterion_id=rubric.criteria[0].id,
                    evidence=[
                        Evidence(
                            source="introduction",
                            quote="built a recommendation service at Zoho",
                        )
                    ],
                    points_awarded=20,
                    points_possible=rubric.criteria[0].points,
                )
            ],
            total_score=20,
            matched_skills=["Python"],
            unevidenced_skills=["Django"],
            resume_intro_conflicts=[],
            assessment="Strong technical background.",
            recommendation="shortlist",
        )

    monkeypatch.setattr(apply_api, "extract_resume", fake_extract_resume)
    # Display-only structuring, and a real model call if left unpatched.
    # It is not what these tests are about, and it must never affect the
    # outcome of an application either way.
    monkeypatch.setattr(apply_api, "try_build_resume_profile", lambda text: None)
    monkeypatch.setattr(apply_api, "transcribe", fake_transcribe)
    monkeypatch.setattr(apply_api, "screen_candidate", fake_screen_candidate)
    monkeypatch.setattr(apply_api.storage, "upload", lambda *a, **k: "path/1.pdf")
    monkeypatch.setattr(
        apply_api.storage,
        "create_candidate",
        lambda **kwargs: {"id": "cand-1", **kwargs},
    )
    monkeypatch.setattr(apply_api.storage, "save_screening", lambda *a, **k: None)
    monkeypatch.setattr(apply_api.storage, "mark_screening_failed", lambda *a, **k: None)

    return {"calls": calls, "job": job_row}


def _post(client, streaming: bool):
    suffix = "/stream" if streaming else ""
    return client.post(
        f"/api/apply/{JOB_ID}{suffix}",
        data={"name": "Priya Nair", "email": "priya@example.com"},
        files={
            "resume": ("resume.pdf", b"fake-pdf-bytes", "application/pdf"),
            "audio": ("introduction.webm", b"fake-audio-bytes", "audio/webm"),
        },
    )


def _lines(response) -> list[dict]:
    return [json.loads(line) for line in response.text.strip().split("\n") if line]


def test_stream_emits_stages_then_result(client, wired):
    response = _post(client, streaming=True)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")

    lines = _lines(response)
    assert lines[0] == {"stage": "reading_resume"}
    assert lines[1] == {"stage": "transcribing"}
    assert lines[2] == {"stage": "scoring"}
    assert "result" in lines[-1]
    assert lines[-1]["result"]["id"] == "cand-1"
    assert lines[-1]["result"]["job_title"] == "Senior Python Developer"


def test_each_stage_is_emitted_before_the_work_it_names(client, wired):
    """The whole point of streaming. A label that appears after its step has
    finished is worse than no label: it names something already done."""
    response = _post(client, streaming=True)
    lines = _lines(response)

    stages = [line["stage"] for line in lines if "stage" in line]
    assert stages == ["reading_resume", "transcribing", "scoring"]
    assert wired["calls"] == ["extract_resume", "transcribe", "screen_candidate"]


def test_streaming_and_plain_routes_return_the_same_result(client, wired):
    """The two routes share one generator specifically so they cannot
    drift. This is the test that would catch it if they did."""
    streamed = _lines(_post(client, streaming=True))[-1]["result"]
    plain = _post(client, streaming=False).json()
    assert streamed == plain


def test_failure_mid_stream_arrives_as_the_standard_error_envelope(
    client, wired, monkeypatch
):
    """Once the first line is sent the status code is committed to 200, so
    the error has to travel in the body. It still has to look exactly like
    every other error the frontend handles."""

    def boom(data, filename):
        raise TranscriptionFailed()

    monkeypatch.setattr(apply_api, "transcribe", boom)

    response = _post(client, streaming=True)
    lines = _lines(response)

    assert response.status_code == 200
    assert lines[0] == {"stage": "reading_resume"}
    assert lines[1] == {"stage": "transcribing"}
    error = lines[-1]["error"]
    assert error["code"] == "transcription_failed"
    assert error["retryable"] is True
    # Candidate-facing prose, never a provider name or a status code.
    assert "could not hear" in error["message"].lower()


def test_stream_never_leaks_an_unexpected_exception(client, wired, monkeypatch):
    """`screen_candidate` failing is deliberately turned into `ScreeningFailed`
    inside `_apply` (the candidate's data must stay saved), so this uses a
    step with no such handling: candidate creation itself."""

    def boom(**kwargs):
        raise RuntimeError("supabase exploded, connection string is postgres://u:p@h")

    monkeypatch.setattr(apply_api.storage, "create_candidate", boom)

    lines = _lines(_post(client, streaming=True))
    error = lines[-1]["error"]

    assert error["code"] == "internal_error"
    assert "postgres" not in error["message"]
    assert "supabase" not in error["message"].lower()

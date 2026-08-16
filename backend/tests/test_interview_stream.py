"""The streamed interview turn.

`/answer` and `/answer/stream` run the same generator, so these tests are
mostly about the two things streaming adds: that a stage name reaches the
browser *before* the work it describes rather than after, and that a
failure after the response has started still arrives in the one error
shape the frontend knows how to render.

Storage, transcription and Gemini are all mocked. What is under test is the
route contract, not the providers.
"""

from __future__ import annotations

import json

import pytest

from app.api import interview as interview_api
from app.core.errors import TranscriptionFailed
from app.models import AnswerScore, InterviewPlan, PlannedQuestion, TurnResult
from tests.fixtures.rubrics import valid_rubric

TOKEN = "test-token"


def _plan(rubric, total: int) -> InterviewPlan:
    """A plan shaped enough to drive the stream.

    Not run through validate_plan: these tests are about stage ordering and
    the error envelope, and the mix rules are covered in test_interview.py.
    """
    ids = [c.id for c in rubric.criteria]
    kinds = ["experience", "resume", "technical", "followup"]
    questions = [
        PlannedQuestion(
            slot=i + 1,
            kind=kinds[i % len(kinds)],
            intent=f"probe {ids[i % len(ids)]}",
            anchor="their internship" if kinds[i % len(kinds)] == "resume" else None,
            criterion_ids=[ids[i % len(ids)]],
            depth="opening" if i < 2 else "probing",
        )
        for i in range(total)
    ]
    return InterviewPlan(questions=questions)


@pytest.fixture
def wired(monkeypatch):
    """Patch the whole turn so only ordering and shape are exercised.

    `calls` records every side effect in the order it happened, which is how
    the stage-before-work assertions below are made.
    """
    rubric = valid_rubric()
    total = 4
    calls: list[str] = []

    interview_row = {
        "id": "interview-1",
        "status": "in_progress",
        "plan": _plan(rubric, total).model_dump(),
        "state_object": None,
        "total_questions": total,
    }
    candidate_row = {"id": "cand-1", "name": "Priya Nair"}

    monkeypatch.setattr(
        interview_api,
        "_load",
        lambda token: (interview_row, candidate_row, {"title": "Senior Python"}, rubric),
    )

    def fake_transcribe(data, filename):
        calls.append("transcribe")
        return "I built a recommendation service at Zoho."

    def fake_advance(rubric_, plan_, state_, slot_, transcript_, is_final_, candidate_=None):
        calls.append("advance_turn")
        return TurnResult(
            answer_scores=[
                AnswerScore(
                    criterion_id=rubric.criteria[0].id,
                    evidence="built a recommendation service",
                    points_awarded=6,
                    points_possible=10,
                )
            ],
            topics_identified=["recommendations"],
            claims_made=["built a recommendation service at Zoho"],
            next_question="How did you handle the cold-start problem?",
            targets_criterion_ids=[rubric.criteria[0].id],
        )

    monkeypatch.setattr(interview_api, "transcribe", fake_transcribe)
    monkeypatch.setattr(interview_api, "advance_turn", fake_advance)
    monkeypatch.setattr(interview_api.storage, "upload", lambda *a, **k: "path/1.webm")
    monkeypatch.setattr(interview_api.storage, "save_answer", lambda *a, **k: None)
    monkeypatch.setattr(
        interview_api.storage, "update_interview_state", lambda *a, **k: None
    )
    monkeypatch.setattr(interview_api.storage, "create_turn", lambda *a, **k: None)
    monkeypatch.setattr(interview_api.storage, "complete_interview", lambda *a, **k: None)
    monkeypatch.setattr(
        interview_api.storage, "set_candidate_state", lambda *a, **k: None
    )
    monkeypatch.setattr(interview_api, "_evaluate", lambda *a, **k: calls.append("evaluate"))

    return {"calls": calls, "interview": interview_row, "total": total}


def _post(client, slot: int, streaming: bool):
    suffix = "/stream" if streaming else ""
    return client.post(
        f"/api/interview/{TOKEN}/answer{suffix}",
        data={"slot": str(slot), "response_time_seconds": "31"},
        files={"audio": ("answer.webm", b"fake-audio-bytes", "audio/webm")},
    )


def _lines(response) -> list[dict]:
    return [json.loads(line) for line in response.text.strip().split("\n") if line]


def test_stream_emits_stages_then_result(client, wired):
    response = _post(client, 1, streaming=True)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")

    lines = _lines(response)
    assert lines[0] == {"stage": "transcribing"}
    assert lines[1] == {"stage": "preparing"}
    assert "result" in lines[-1]
    assert lines[-1]["result"]["next_slot"] == 2
    assert lines[-1]["result"]["status"] == "in_progress"


def test_each_stage_is_emitted_before_the_work_it_names(client, wired):
    """The whole point of streaming. A label that appears after its step has
    finished is worse than no label: it names something already done."""
    response = _post(client, 1, streaming=True)
    lines = _lines(response)

    stages = [line["stage"] for line in lines if "stage" in line]
    assert stages == ["transcribing", "preparing"]
    # And the side effects happened in the matching order.
    assert wired["calls"] == ["transcribe", "advance_turn"]


def test_final_slot_announces_reviewing_not_preparing(client, wired):
    """There is no next question on the last turn, so claiming to prepare
    one would be a lie. The slow step there is evaluation."""
    response = _post(client, wired["total"], streaming=True)
    lines = _lines(response)

    stages = [line["stage"] for line in lines if "stage" in line]
    assert stages == ["transcribing", "reviewing"]
    assert lines[-1]["result"]["status"] == "complete"
    assert lines[-1]["result"]["next_question"] is None


def test_streaming_and_plain_routes_return_the_same_result(client, wired):
    """The two routes share one generator specifically so they cannot
    drift. This is the test that would catch it if they did."""
    streamed = _lines(_post(client, 1, streaming=True))[-1]["result"]
    plain = _post(client, 1, streaming=False).json()
    assert streamed == plain


def test_failure_mid_stream_arrives_as_the_standard_error_envelope(
    client, wired, monkeypatch
):
    """Once the first line is sent the status code is committed to 200, so
    the error has to travel in the body. It still has to look exactly like
    every other error the frontend handles."""

    def boom(data, filename):
        raise TranscriptionFailed()

    monkeypatch.setattr(interview_api, "transcribe", boom)

    response = _post(client, 1, streaming=True)
    lines = _lines(response)

    assert response.status_code == 200
    assert lines[0] == {"stage": "transcribing"}
    error = lines[-1]["error"]
    assert error["code"] == "transcription_failed"
    assert error["retryable"] is True
    # Candidate-facing prose, never a provider name or a status code.
    assert "could not hear" in error["message"].lower()


def test_stream_never_leaks_an_unexpected_exception(client, wired, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("supabase exploded, connection string is postgres://u:p@h")

    monkeypatch.setattr(interview_api, "advance_turn", boom)

    lines = _lines(_post(client, 1, streaming=True))
    error = lines[-1]["error"]

    assert error["code"] == "internal_error"
    assert "postgres" not in error["message"]
    assert "supabase" not in error["message"].lower()

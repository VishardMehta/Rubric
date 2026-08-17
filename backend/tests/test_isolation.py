"""Interview isolation: one candidate, one interview, one set of answers.

The interview is the part of the product where a leak would be worst. A
transcript is someone talking about their work for ten minutes, and the
token in the URL is the only thing standing between a stranger and it.

These run against the in-memory store rather than mocks of storage, so the
rows really are written and really are read back, and a route that returned
the wrong row would fail here rather than pass against a mock that was told
what to return.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import interview as interview_api
from app.integrations import storage
from app.integrations.demo_supabase import DemoClient
from app.main import create_app
from app.models import InterviewPlan, PlannedQuestion
from tests.fixtures.rubrics import valid_rubric


@pytest.fixture
def store(monkeypatch) -> DemoClient:
    client = DemoClient({})
    monkeypatch.setattr(storage, "get_client", lambda: client)
    return client


@pytest.fixture
def api(store) -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def two_candidates(store, monkeypatch):
    """Two people, same job, both approved for interview."""
    rubric = valid_rubric()
    job = storage.create_job(
        "Senior Python Developer", "d" * 200, ["Python"], None, owner_id="hr-1"
    )
    storage.set_job_rubric(job["id"], rubric)

    def _apply(name: str, email: str) -> dict:
        candidate = storage.create_candidate(
            job_id=job["id"],
            name=name,
            email=email,
            resume_path=f"resumes/{email}.pdf",
            resume_text=f"{name} built things",
            audio_path=f"introductions/{email}.webm",
            transcript=f"{name} speaking",
        )
        storage.set_candidate_state(candidate["id"], "approved")
        result = storage.approve_candidate_atomic(candidate["id"], f"tok-{email}")
        return {"candidate": candidate, "token": result["token"]}

    # The plan is the one model call in this flow. Everything else here is
    # real: real rows, real reads, real route code.
    ids = [c.id for c in rubric.criteria]
    kinds = ["experience", "resume", "technical", "followup"]
    plan = InterviewPlan(
        questions=[
            PlannedQuestion(
                slot=i + 1,
                kind=kinds[i % len(kinds)],
                intent=f"probe {ids[i % len(ids)]}",
                anchor="their internship" if kinds[i % len(kinds)] == "resume" else None,
                criterion_ids=[ids[i % len(ids)]],
                depth="opening" if i < 2 else "probing",
            )
            for i in range(4)
        ]
    )
    monkeypatch.setattr(interview_api, "generate_plan", lambda *a, **k: plan)

    return {"a": _apply("Priya Nair", "priya@example.com"),
            "b": _apply("Arun Menon", "arun@example.com")}


def test_each_candidate_gets_their_own_token(two_candidates):
    assert two_candidates["a"]["token"] != two_candidates["b"]["token"]


def test_a_token_opens_its_own_interview_and_names_its_own_candidate(api, two_candidates):
    a = api.get(f"/api/interview/{two_candidates['a']['token']}").json()
    b = api.get(f"/api/interview/{two_candidates['b']['token']}").json()

    assert a["candidate_name"] == "Priya Nair"
    assert b["candidate_name"] == "Arun Menon"


def test_an_unknown_token_opens_nothing(api, two_candidates):
    response = api.get("/api/interview/not-a-real-token")
    assert response.status_code == 404
    assert "Arun" not in response.text and "Priya" not in response.text


def test_starting_one_interview_does_not_start_the_other(api, two_candidates, store):
    started = api.post(f"/api/interview/{two_candidates['a']['token']}/start")
    assert started.status_code == 200
    assert started.json()["current_slot"] == 1

    other = api.get(f"/api/interview/{two_candidates['b']['token']}").json()
    assert other["status"] == "not_started"
    assert other["current_slot"] is None

    # And the state each one carries belongs to it alone.
    interviews = {i["candidate_id"]: i for i in store.snapshot()["interviews"]}
    a_row = interviews[two_candidates["a"]["candidate"]["id"]]
    b_row = interviews[two_candidates["b"]["candidate"]["id"]]
    assert a_row["status"] == "in_progress" and a_row["plan"] is not None
    assert b_row["status"] == "not_started" and b_row.get("plan") is None


def test_a_question_is_written_only_to_the_interview_it_belongs_to(api, two_candidates, store):
    api.post(f"/api/interview/{two_candidates['a']['token']}/start")

    turns = store.snapshot()["interview_turns"]
    interviews = {i["candidate_id"]: i["id"] for i in store.snapshot()["interviews"]}
    a_id = interviews[two_candidates["a"]["candidate"]["id"]]
    b_id = interviews[two_candidates["b"]["candidate"]["id"]]

    assert [t["interview_id"] for t in turns] == [a_id]
    assert not [t for t in turns if t["interview_id"] == b_id]


def test_starting_twice_resumes_rather_than_replanning(api, two_candidates, store):
    """A refresh on the interview screen must not discard progress."""
    first = api.post(f"/api/interview/{two_candidates['a']['token']}/start").json()
    second = api.post(f"/api/interview/{two_candidates['a']['token']}/start").json()

    assert first["current_question"] == second["current_question"]
    assert len(store.snapshot()["interview_turns"]) == 1

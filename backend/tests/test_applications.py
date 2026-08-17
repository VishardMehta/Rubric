"""The candidate portal.

One rule dominates this file: the candidate never sees a score, at any
point, including on completion (product.md section 2). This endpoint is the
most likely place in the API for one to leak, because it is the only
candidate-facing response built from a candidate row, and that row carries
screening_score, screening_band, recommendation, sub_scores and assessment.

The leak test below asserts on the serialized response rather than on the
model, so adding a field to CandidateApplication that happens to carry a
score fails here even if it type checks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.integrations import storage
from app.integrations.demo_supabase import DemoClient
from app.main import create_app

FORBIDDEN_KEYS = (
    "screening_score",
    "screening_band",
    "recommendation",
    "sub_scores",
    "assessment",
    "matched_skills",
    "unevidenced_skills",
    "resume_intro_conflicts",
    "resume_text",
    "resume_profile",
    "transcript",
)


@pytest.fixture
def store(monkeypatch) -> DemoClient:
    client = DemoClient({})
    monkeypatch.setattr(storage, "get_client", lambda: client)
    return client


@pytest.fixture
def api(store) -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def applicant(store):
    """One scored, rejected-capable applicant with a full set of scores."""
    job = storage.create_job("Junior Business Analyst", "d" * 200, ["SQL"], None, owner_id="hr-1")
    candidate = storage.create_candidate(
        job_id=job["id"],
        name="Priyanshu Singh",
        email="applicant@example.com",
        resume_path="resumes/x.pdf",
        resume_text="resume text",
        audio_path="introductions/x.webm",
        transcript="spoken introduction",
    )
    storage.save_screening(
        candidate["id"],
        score=61,
        band="borderline",
        resume_score=70,
        voice_score=47,
        sub_scores=[{"criterion_id": "a", "points_awarded": 70, "points_possible": 100}],
        voice_sub_scores=[{"criterion_id": "a", "points_awarded": 47, "points_possible": 100}],
        matched_skills=["SQL"],
        unevidenced_skills=["Tableau"],
        conflicts=[],
        assessment="A long prose assessment for the hiring team only.",
        recommendation="review",
    )
    return {"job": job, "candidate": candidate}


def test_a_new_candidate_sees_nothing_even_with_demo_auth_on(api, applicant, monkeypatch):
    """The isolation rule, and the regression this file exists to prevent.

    There used to be a DEMO_AUTH fallback that showed every application on
    file when the address had none, so a brand new candidate saw sixteen
    applications belonging to other people. An empty list is the only
    correct answer for someone who has not applied to anything, whatever
    the demo flags say.
    """
    monkeypatch.setenv("DEMO_AUTH", "1")
    get_settings.cache_clear()
    try:
        mine = api.get("/api/applications?email=applicant@example.com")
        assert mine.status_code == 200
        assert len(mine.json()) == 1, "the address that applied still sees its own"

        nobody = api.get("/api/applications?email=nobody@example.com")
        assert nobody.status_code == 200
        assert nobody.json() == []
    finally:
        get_settings.cache_clear()


def _walk(node):
    """Every key and every scalar value in a parsed JSON tree."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield ("key", key)
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)
    else:
        yield ("value", node)


def test_the_portal_never_returns_a_score_or_anything_near_one(api, applicant):
    response = api.get("/api/applications", params={"email": "applicant@example.com"})
    assert response.status_code == 200

    pairs = list(_walk(response.json()))
    keys = {name for kind, name in pairs if kind == "key"}
    values = {v for kind, v in pairs if kind == "value"}

    for forbidden in FORBIDDEN_KEYS:
        assert forbidden not in keys, f"{forbidden} leaked to the candidate"

    # Compared as whole values rather than substrings. A raw `"61" in body`
    # matches any UUID containing those digits, and `"review"` matches this
    # endpoint's own in_review status, so both produce false failures.
    assert 61 not in values
    assert "61" not in values
    assert "borderline" not in values
    assert "review" not in values
    assert not any(
        isinstance(v, str) and "prose assessment" in v for v in values
    )


def test_the_candidate_sees_their_own_applications(api, applicant):
    rows = api.get("/api/applications", params={"email": "applicant@example.com"}).json()
    assert len(rows) == 1
    assert rows[0]["job_title"] == "Junior Business Analyst"
    assert rows[0]["status"] == "in_review"
    assert rows[0]["interview_url"] is None


def test_a_capitalised_email_finds_the_same_applications(api, applicant):
    rows = api.get("/api/applications", params={"email": " Applicant@Example.COM "}).json()
    assert len(rows) == 1


def test_an_unknown_email_returns_an_empty_list_not_an_error(api, applicant):
    response = api.get("/api/applications", params={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert response.json() == []


def test_a_rejected_application_reads_as_closed_with_no_number(api, applicant):
    """The candidate is told the outcome, not the judgement behind it."""
    storage.set_candidate_state(applicant["candidate"]["id"], "rejected")

    rows = api.get("/api/applications", params={"email": "applicant@example.com"}).json()
    assert rows[0]["status"] == "closed"
    assert rows[0]["status_label"] == "Closed"
    assert "reject" not in rows[0]["status_detail"].lower()
    assert 61 not in {v for kind, v in _walk(rows[0]) if kind == "value"}


def test_the_interview_link_appears_only_after_it_is_sent(api, applicant):
    """A token minted is not a token sent. The portal surfaces a link only
    once HR has actually invited them."""
    candidate_id = applicant["candidate"]["id"]

    # Approved, but the invitation not yet stamped.
    storage.set_candidate_state(candidate_id, "approved")
    interview = storage.create_interview(candidate_id, "tok-not-sent")

    rows = api.get("/api/applications", params={"email": "applicant@example.com"}).json()
    assert rows[0]["status"] == "interview_ready"
    assert rows[0]["interview_url"] is None

    storage.mark_interview_invited(interview["id"])
    rows = api.get("/api/applications", params={"email": "applicant@example.com"}).json()
    assert rows[0]["interview_url"] == "/interview/tok-not-sent"


def test_a_finished_interview_withdraws_the_link(api, applicant, store):
    """A completed link should not be reopenable from the portal."""
    candidate_id = applicant["candidate"]["id"]
    storage.set_candidate_state(candidate_id, "interviewed")
    interview = storage.create_interview(candidate_id, "tok-done")
    storage.mark_interview_invited(interview["id"])
    storage.complete_interview(interview["id"], {})

    rows = api.get("/api/applications", params={"email": "applicant@example.com"}).json()
    assert rows[0]["status"] == "interview_complete"
    assert rows[0]["interview_url"] is None


def test_the_portal_needs_no_session(api, applicant):
    """The whole candidate side is unauthenticated by design."""
    assert "Authorization" not in api.headers
    assert api.get("/api/applications", params={"email": "applicant@example.com"}).status_code == 200

"""API route tests. Storage and Gemini are both mocked - these assert the
route contract (what is saved, in what order, what is exposed), not the
providers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.api import jobs as jobs_api
from tests.conftest import HR_TEST_USER
from tests.fixtures.rubrics import valid_rubric

JOB_ROW = {
    "id": "job-1",
    "title": "Senior Python Developer",
    "description": "We need someone to build and run our Django services." * 4,
    "skills": ["Python", "Django", "PostgreSQL"],
    "experience": "2 to 4 years",
    "state": "analyzing",
    "created_at": "2026-08-14T10:00:00Z",
    "rubric": None,
    # Owned by the account the `client` fixture is signed in as. Without
    # this the ownership check refuses every one of these rows and the
    # tests fail with a 404 that has nothing to do with what they assert.
    "owner_id": HR_TEST_USER.id,
}


def _active_row(rubric_dict: dict) -> dict:
    return {**JOB_ROW, "state": "active", "rubric": rubric_dict}


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Reported so the sign in screen can say when the auth bypass is on.
    assert body["demo_auth"] is False


def test_create_job_saves_before_generating(client, monkeypatch):
    """Order matters: the job row must exist before rubric generation runs,
    so a generation failure leaves HR's description saved rather than lost
    (screens.md section 2 error state)."""
    order: list[str] = []
    rubric = valid_rubric()

    def fake_create_job(**kwargs):
        order.append("insert")
        return dict(JOB_ROW)

    def fake_generate(*args, **kwargs):
        order.append("generate")
        return rubric

    def fake_set_rubric(job_id, r):
        order.append("update")
        return _active_row(r.model_dump())

    monkeypatch.setattr(jobs_api.storage, "create_job", fake_create_job)
    monkeypatch.setattr(jobs_api, "_generate_rubric", fake_generate)
    monkeypatch.setattr(jobs_api.storage, "set_job_rubric", fake_set_rubric)

    response = client.post(
        "/api/jobs",
        json={
            "title": "Senior Python Developer",
            "description": JOB_ROW["description"],
            "skills": ["Python", "Django"],
            "experience": "2 to 4 years",
        },
    )

    assert response.status_code == 200
    assert order == ["insert", "generate", "update"]

    body = response.json()
    assert body["state"] == "active"
    assert len(body["rubric"]["criteria"]) == 5
    assert sum(c["points"] for c in body["rubric"]["criteria"]) == 100


def test_create_job_generation_failure_returns_retryable_error(client, monkeypatch):
    monkeypatch.setattr(jobs_api.storage, "create_job", lambda **kw: dict(JOB_ROW))

    def boom(*args, **kwargs):
        raise RuntimeError("provider timed out")

    monkeypatch.setattr(jobs_api, "_generate_rubric", boom)
    updated = MagicMock()
    monkeypatch.setattr(jobs_api.storage, "set_job_rubric", updated)

    response = client.post(
        "/api/jobs",
        json={"title": "X", "description": "Y", "skills": [], "experience": None},
    )

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "rubric_generation_failed"
    assert error["retryable"] is True
    # The prose is user facing: no provider name, no stack trace.
    assert "provider timed out" not in error["message"]
    assert "saved" in error["message"]
    # The row is not marked active when generation failed.
    updated.assert_not_called()


def test_list_jobs_includes_pipeline_counts(client, monkeypatch):
    seen: dict = {}

    def fake_list_jobs(owner_id=None):
        seen["owner_id"] = owner_id
        return [dict(JOB_ROW)]

    monkeypatch.setattr(jobs_api.storage, "list_jobs", fake_list_jobs)
    monkeypatch.setattr(
        jobs_api.storage,
        "pipeline_counts",
        lambda ids: {"job-1": {"applicant": 48, "shortlisted": 12, "interviewed": 7}},
    )

    response = client.get("/api/jobs")

    assert response.status_code == 200
    row = response.json()[0]
    assert row["applicant_count"] == 48
    assert row["shortlisted_count"] == 12
    assert row["interviewed_count"] == 7
    # The dashboard must never fall back to an unscoped list. Without the
    # owner_id every account would see every account's roles.
    assert seen["owner_id"] == HR_TEST_USER.id


def test_get_job_returns_rubric(client, monkeypatch):
    rubric = valid_rubric()
    monkeypatch.setattr(
        jobs_api.storage, "get_job", lambda job_id: _active_row(rubric.model_dump())
    )
    monkeypatch.setattr(
        jobs_api.storage,
        "pipeline_counts",
        lambda ids: {"job-1": {"applicant": 0, "shortlisted": 0, "interviewed": 0}},
    )

    response = client.get("/api/jobs/job-1")

    assert response.status_code == 200
    assert response.json()["rubric"]["criteria"][0]["id"] == "python_and_django"


def test_get_missing_job_is_not_a_500(client, monkeypatch):
    monkeypatch.setattr(jobs_api.storage, "get_job", lambda job_id: None)
    response = client.get("/api/jobs/nope")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "job_not_active"


def test_public_apply_summary_exposes_role_context_but_never_the_rubric(client, monkeypatch):
    """Candidates need enough context to browse roles, not the scoring key."""
    rubric = valid_rubric()
    monkeypatch.setattr(
        jobs_api.storage, "get_job", lambda job_id: _active_row(rubric.model_dump())
    )

    response = client.get("/api/apply/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Senior Python Developer"
    assert body["description"] == JOB_ROW["description"]
    assert body["skills"] == JOB_ROW["skills"]
    assert "rubric" not in body
    # Belt and braces: no criterion name leaks through any field.
    assert "python_and_django" not in response.text


def test_job_description_pdf_is_extracted_for_hr_review(client, monkeypatch):
    """The uploaded PDF is read into an editable field; it is not persisted."""
    monkeypatch.setattr(
        jobs_api,
        "_job_document_text",
        lambda data: "A clear role description extracted from the source PDF.",
    )
    monkeypatch.setattr(jobs_api, "_parse_job_facts", lambda text: None)

    response = client.post(
        "/api/jobs/description-document",
        files={"document": ("role.pdf", b"%PDF-source", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "A clear role description extracted from the source PDF."
    assert body["facts"] is None


def test_a_job_description_that_cannot_be_parsed_still_returns_its_text(client, monkeypatch):
    """Parsing is an aid, not a gate.

    A rate limited or unusable model must not stop HR posting a role: the
    raw text is exactly what this endpoint returned before parsing existed,
    so the failure degrades to the old behavior instead of a 502.
    """
    monkeypatch.setattr(jobs_api, "_job_document_text", lambda data: "Role text " * 20)

    def exploding_parse(*args, **kwargs):
        raise RuntimeError("provider is unhappy")

    monkeypatch.setattr(jobs_api, "generate_structured", exploding_parse)

    response = client.post(
        "/api/jobs/description-document",
        files={"document": ("role.pdf", b"%PDF-source", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["facts"] is None
    assert response.json()["text"].startswith("Role text")


def test_job_facts_are_saved_as_columns_not_appended_to_the_description(client, monkeypatch):
    """These used to be flattened into the description string by the
    frontend, which meant they could never be read back out or shown to a
    candidate as fields."""
    seen: dict = {}
    rubric = valid_rubric()

    def fake_create_job(**kwargs):
        seen.update(kwargs)
        return dict(JOB_ROW)

    monkeypatch.setattr(jobs_api.storage, "create_job", fake_create_job)
    monkeypatch.setattr(jobs_api, "_generate_rubric", lambda *a, **k: rubric)
    monkeypatch.setattr(
        jobs_api.storage, "set_job_rubric", lambda job_id, r: _active_row(r.model_dump())
    )

    response = client.post(
        "/api/jobs",
        json={
            "title": "Junior Business Analyst",
            "description": "d" * 200,
            "skills": ["SQL"],
            "location": "Hyderabad",
            "employment_type": "internship",
            "compensation": "18 to 24 LPA",
            # Blank, so it should be dropped rather than stored as "".
            "department": "   ",
        },
    )

    assert response.status_code == 200
    assert seen["facts"] == {
        "location": "Hyderabad",
        "employment_type": "internship",
        "compensation": "18 to 24 LPA",
    }
    assert "Hyderabad" not in seen["description"]


def test_public_apply_summary_rejects_inactive_job(client, monkeypatch):
    monkeypatch.setattr(jobs_api.storage, "get_job", lambda job_id: dict(JOB_ROW))
    response = client.get("/api/apply/job-1")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "job_not_active"


def test_regenerate_rubric_reuses_saved_description(client, monkeypatch):
    rubric = valid_rubric()
    seen: dict = {}

    monkeypatch.setattr(jobs_api.storage, "get_job", lambda job_id: dict(JOB_ROW))

    def fake_generate(title, description, skills, experience):
        seen.update(title=title, description=description, skills=skills)
        return rubric

    monkeypatch.setattr(jobs_api, "_generate_rubric", fake_generate)
    monkeypatch.setattr(
        jobs_api.storage, "set_job_rubric", lambda jid, r: _active_row(r.model_dump())
    )
    monkeypatch.setattr(
        jobs_api.storage,
        "pipeline_counts",
        lambda ids: {"job-1": {"applicant": 0, "shortlisted": 0, "interviewed": 0}},
    )

    response = client.post("/api/jobs/job-1/rubric/regenerate")

    assert response.status_code == 200
    assert seen["title"] == JOB_ROW["title"]
    assert seen["skills"] == JOB_ROW["skills"]


def test_candidate_detail_carries_the_interview_token_and_status(client, monkeypatch):
    """screens.md section 4 needs both of these to render.

    The token drives the post-approval interview link, and the status
    decides whether a link to the interview result is offered. Both are
    declared on CandidateDetail, and the route returned null for both until
    this was caught - so the response satisfied its own schema while making
    two documented states unreachable in the UI.
    """
    from app.api import candidates as candidates_api

    monkeypatch.setattr(
        candidates_api.storage,
        "get_candidate",
        lambda cid: {
            "id": cid,
            "job_id": "job-1",
            "name": "Priya Nair",
            "email": "priya@example.com",
            "state": "interviewed",
            "created_at": "2026-08-14T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        candidates_api.storage,
        "get_job",
        lambda jid: {
            "id": jid,
            "title": "Senior Python",
            "skills": [],
            "owner_id": HR_TEST_USER.id,
        },
    )
    monkeypatch.setattr(
        candidates_api.storage,
        "get_interview_by_candidate",
        lambda cid: {"id": "int-1", "token": "tok-abc", "status": "evaluated"},
    )
    monkeypatch.setattr(candidates_api.storage, "signed_url", lambda *a, **k: None)

    body = client.get("/api/candidates/cand-1").json()

    assert body["interview_token"] == "tok-abc"
    assert body["interview_status"] == "evaluated"


def test_candidate_detail_omits_interview_fields_when_none_exists(client, monkeypatch):
    """A candidate who has not been approved has no interview, and the
    screen must not offer a link to one."""
    from app.api import candidates as candidates_api

    monkeypatch.setattr(
        candidates_api.storage,
        "get_candidate",
        lambda cid: {
            "id": cid,
            "job_id": "job-1",
            "name": "Kavya Rao",
            "email": "kavya@example.com",
            "state": "screened",
            "created_at": "2026-08-14T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        candidates_api.storage,
        "get_job",
        lambda jid: {
            "id": jid,
            "title": "Senior Python",
            "skills": [],
            "owner_id": HR_TEST_USER.id,
        },
    )
    monkeypatch.setattr(
        candidates_api.storage, "get_interview_by_candidate", lambda cid: None
    )
    monkeypatch.setattr(candidates_api.storage, "signed_url", lambda *a, **k: None)

    body = client.get("/api/candidates/cand-2").json()

    assert body["interview_token"] is None
    assert body["interview_status"] is None

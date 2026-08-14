"""API route tests. Storage and Gemini are both mocked - these assert the
route contract (what is saved, in what order, what is exposed), not the
providers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.api import jobs as jobs_api
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
}


def _active_row(rubric_dict: dict) -> dict:
    return {**JOB_ROW, "state": "active", "rubric": rubric_dict}


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    monkeypatch.setattr(jobs_api.storage, "list_jobs", lambda: [dict(JOB_ROW)])
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


def test_public_apply_summary_never_exposes_the_rubric(client, monkeypatch):
    """A candidate who could read the rubric would know exactly what to say.
    backend.md section 4: title only."""
    rubric = valid_rubric()
    monkeypatch.setattr(
        jobs_api.storage, "get_job", lambda job_id: _active_row(rubric.model_dump())
    )

    response = client.get("/api/apply/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Senior Python Developer"
    assert "rubric" not in body
    assert "description" not in body
    # Belt and braces: no criterion name leaks through any field.
    assert "python_and_django" not in response.text


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

"""HR accounts, sessions, and the ownership boundary.

The ownership tests are the point of this file. Before Phase A any caller
could read any candidate's transcript, resume URL and scores by walking
candidate ids, because nothing tied a job to an account. Every one of
those routes now resolves candidate to job to owner, and an IDOR is what
you get if a future route forgets. Each protected route is listed here by
name so adding one without a test is a visible omission.

These run against the in-memory store rather than mocks, so the real
storage functions, the real unique constraints and the real RPC path all
execute. No network, no cassettes, no LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.integrations import storage
from app.integrations.demo_supabase import DemoClient
from app.main import create_app
from app.services.accounts import hash_password, normalise_email, verify_password


@pytest.fixture
def store(monkeypatch) -> DemoClient:
    """A fresh empty database for each test."""
    client = DemoClient({})
    monkeypatch.setattr(storage, "get_client", lambda: client)
    return client


@pytest.fixture
def api(store) -> TestClient:
    return TestClient(create_app())


def register(api: TestClient, email: str, password: str = "correct-horse-1") -> dict:
    response = api.post(
        "/api/auth/register",
        json={"email": email, "name": "Recruiter", "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------


def test_a_password_verifies_against_its_own_hash():
    digest, salt = hash_password("correct-horse-1")
    assert verify_password("correct-horse-1", digest, salt)
    assert not verify_password("correct-horse-2", digest, salt)


def test_the_same_password_hashes_differently_for_two_accounts():
    """A per-account salt. Without it, two people who pick the same
    password share a hash, and cracking one cracks both."""
    first_hash, first_salt = hash_password("correct-horse-1")
    second_hash, second_salt = hash_password("correct-horse-1")
    assert first_salt != second_salt
    assert first_hash != second_hash


def test_the_stored_hash_is_not_the_password():
    digest, _ = hash_password("correct-horse-1")
    assert "correct-horse-1" not in digest


def test_a_corrupt_salt_fails_the_login_rather_than_raising():
    """A damaged row should look exactly like a wrong password, not like a
    500 that tells the caller the account exists."""
    digest, _ = hash_password("correct-horse-1")
    assert not verify_password("correct-horse-1", digest, "not-hex")


def test_email_is_normalised():
    assert normalise_email("  HR@Example.COM ") == "hr@example.com"


# ---------------------------------------------------------------------
# Registration and login
# ---------------------------------------------------------------------


def test_registration_returns_a_working_session(api):
    session = register(api, "first@example.com")
    assert session["token"]
    me = api.get("/api/auth/me", headers=auth(session["token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "first@example.com"


def test_registration_never_returns_the_password_hash(api):
    """The account shape the frontend receives carries no credential
    material at all, so no component can accidentally render one."""
    session = register(api, "first@example.com")
    body = str(session)
    assert "password" not in body
    assert set(session["account"]) == {"id", "email", "name", "company"}


def test_a_capitalised_email_reaches_the_same_account(api):
    register(api, "first@example.com")
    response = api.post(
        "/api/auth/login",
        json={"email": "  First@Example.COM ", "password": "correct-horse-1"},
    )
    assert response.status_code == 200


def test_a_duplicate_email_is_refused(api):
    register(api, "first@example.com")
    response = api.post(
        "/api/auth/register",
        json={"email": "first@example.com", "name": "Other", "password": "correct-horse-1"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


def test_a_short_password_is_refused(api):
    response = api.post(
        "/api/auth/register",
        json={"email": "first@example.com", "name": "R", "password": "short"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weak_password"


def test_a_wrong_password_and_an_unknown_email_give_the_same_answer(api):
    """Distinguishing them turns login into an oracle for which addresses
    have accounts."""
    register(api, "first@example.com")

    wrong_password = api.post(
        "/api/auth/login",
        json={"email": "first@example.com", "password": "not-the-password"},
    )
    unknown_email = api.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "correct-horse-1"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


# ---------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------


def test_every_hr_route_refuses_an_anonymous_caller(api):
    for method, path in [
        ("get", "/api/jobs"),
        ("post", "/api/jobs"),
        ("get", "/api/jobs/any/candidates"),
        ("get", "/api/jobs/any"),
        ("post", "/api/jobs/any/rubric/regenerate"),
        ("get", "/api/candidates/any"),
        ("post", "/api/candidates/any/approve"),
        ("post", "/api/candidates/any/reject"),
        ("post", "/api/candidates/any/hire"),
        ("post", "/api/candidates/any/rescreen"),
        ("get", "/api/candidates/any/interview"),
        ("post", "/api/candidates/any/interview/evaluate"),
        ("get", "/api/auth/me"),
    ]:
        kwargs = {"json": {}} if method == "post" else {}
        response = getattr(api, method)(path, **kwargs)
        assert response.status_code == 401, f"{method.upper()} {path} did not require a session"
        assert response.json()["error"]["code"] == "not_authenticated"


def test_the_candidate_facing_routes_stay_public(api):
    """The whole candidate side is unauthenticated by design (product.md
    section 5). A blanket auth middleware would have broken these, which is
    why the check is a per-route dependency instead."""
    assert api.get("/api/health").status_code == 200
    assert api.get("/api/apply").status_code == 200
    # Not 401: a missing job, which is the correct answer for a public
    # route asked about something that does not exist.
    assert api.get("/api/apply/does-not-exist").status_code != 401
    assert api.get("/api/interview/does-not-exist").status_code != 401


def test_a_garbage_token_is_refused(api):
    assert api.get("/api/jobs", headers=auth("not-a-real-token")).status_code == 401


def test_a_malformed_authorization_header_is_refused(api):
    for header in ["", "Bearer", "Basic abc", "abc"]:
        response = api.get("/api/jobs", headers={"Authorization": header})
        assert response.status_code == 401


def test_an_expired_session_is_refused_and_deleted(api, store):
    session = register(api, "first@example.com")
    account_id = session["account"]["id"]

    stale = "expired-token"
    storage.create_session(
        stale, account_id, (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    )
    assert storage.get_session(stale) is not None

    assert api.get("/api/jobs", headers=auth(stale)).status_code == 401
    # Cleaned up rather than merely rejected, so expired rows do not
    # accumulate forever.
    assert storage.get_session(stale) is None


def test_logout_invalidates_the_session(api):
    session = register(api, "first@example.com")
    token = session["token"]
    assert api.get("/api/jobs", headers=auth(token)).status_code == 200

    assert api.post("/api/auth/logout", headers=auth(token)).status_code == 200
    assert api.get("/api/jobs", headers=auth(token)).status_code == 401


def test_logging_out_twice_is_not_an_error(api):
    """The frontend calls this on a 401 as part of clearing local state. It
    must not fail when the session is already gone."""
    session = register(api, "first@example.com")
    api.post("/api/auth/logout", headers=auth(session["token"]))
    assert api.post("/api/auth/logout", headers=auth(session["token"])).status_code == 200
    assert api.post("/api/auth/logout").status_code == 200


# ---------------------------------------------------------------------
# The first account claims the rows that predate accounts
# ---------------------------------------------------------------------


def test_the_first_account_claims_ownerless_jobs(api, store):
    """Everything created before accounts existed, including database/seed.sql,
    has a null owner. Without the claim it would be permanently invisible."""
    storage.create_job("Legacy role", "description", ["SQL"], None, owner_id=None)

    session = register(api, "first@example.com")
    assert session["claimed_jobs"] == 1

    jobs = api.get("/api/jobs", headers=auth(session["token"])).json()
    assert [j["title"] for j in jobs] == ["Legacy role"]


def test_the_second_account_claims_nothing(api, store):
    storage.create_job("Legacy role", "description", ["SQL"], None, owner_id=None)

    first = register(api, "first@example.com")
    second = register(api, "second@example.com")

    assert first["claimed_jobs"] == 1
    assert second["claimed_jobs"] == 0
    assert api.get("/api/jobs", headers=auth(second["token"])).json() == []


# ---------------------------------------------------------------------
# Ownership. The IDOR boundary.
# ---------------------------------------------------------------------


@pytest.fixture
def two_accounts(api, store):
    """Account A owns a job with one applicant. Account B owns nothing."""
    a = register(api, "a@example.com")
    b = register(api, "b@example.com")

    job = storage.create_job(
        "A's role", "description", ["SQL"], None, owner_id=a["account"]["id"]
    )
    storage.set_job_rubric(job["id"], _rubric())
    candidate = storage.create_candidate(
        job_id=job["id"],
        name="Applicant",
        email="applicant@example.com",
        resume_path="resumes/x.pdf",
        resume_text="resume text",
        audio_path="introductions/x.webm",
        transcript="spoken introduction",
    )
    return {"a": a, "b": b, "job": job, "candidate": candidate}


def _rubric():
    from tests.fixtures.rubrics import valid_rubric

    return valid_rubric()


def test_an_account_sees_only_its_own_jobs(api, two_accounts):
    a_jobs = api.get("/api/jobs", headers=auth(two_accounts["a"]["token"])).json()
    b_jobs = api.get("/api/jobs", headers=auth(two_accounts["b"]["token"])).json()
    assert [j["title"] for j in a_jobs] == ["A's role"]
    assert b_jobs == []


def test_another_account_cannot_reach_the_job_or_its_applicants(api, two_accounts):
    """The IDOR check, route by route.

    A candidate row carries the transcript, the resume text and signed URLs
    to the original audio and PDF. Every one of these routes returned all
    of that to any caller before ownership existed.
    """
    b = auth(two_accounts["b"]["token"])
    job_id = two_accounts["job"]["id"]
    candidate_id = two_accounts["candidate"]["id"]

    forbidden = [
        ("get", f"/api/jobs/{job_id}"),
        ("get", f"/api/jobs/{job_id}/candidates"),
        ("post", f"/api/jobs/{job_id}/rubric/regenerate"),
        ("get", f"/api/candidates/{candidate_id}"),
        ("post", f"/api/candidates/{candidate_id}/approve"),
        ("post", f"/api/candidates/{candidate_id}/reject"),
        ("post", f"/api/candidates/{candidate_id}/hire"),
        ("post", f"/api/candidates/{candidate_id}/rescreen"),
        ("get", f"/api/candidates/{candidate_id}/interview"),
        ("post", f"/api/candidates/{candidate_id}/interview/evaluate"),
    ]

    for method, path in forbidden:
        response = getattr(api, method)(path, headers=b)
        assert response.status_code in (404, 409), f"{method.upper()} {path} leaked to another account"
        body = response.text
        assert "spoken introduction" not in body
        assert "resume text" not in body
        assert "applicant@example.com" not in body


def test_the_owner_can_reach_what_the_other_account_cannot(api, two_accounts):
    """The mirror of the test above. Without this, scoping everything to
    404 would also pass."""
    a = auth(two_accounts["a"]["token"])
    job_id = two_accounts["job"]["id"]
    candidate_id = two_accounts["candidate"]["id"]

    assert api.get(f"/api/jobs/{job_id}", headers=a).status_code == 200
    assert api.get(f"/api/jobs/{job_id}/candidates", headers=a).status_code == 200

    detail = api.get(f"/api/candidates/{candidate_id}", headers=a)
    assert detail.status_code == 200
    assert detail.json()["transcript"] == "spoken introduction"


def test_a_job_is_stamped_with_its_creator(api, store, monkeypatch):
    from app.api import jobs as jobs_api

    monkeypatch.setattr(jobs_api, "_generate_rubric", lambda *a, **k: _rubric())

    first = register(api, "first@example.com")
    second = register(api, "second@example.com")

    created = api.post(
        "/api/jobs",
        headers=auth(second["token"]),
        json={"title": "B's role", "description": "d" * 200, "skills": ["SQL"]},
    )
    assert created.status_code == 200

    assert api.get("/api/jobs", headers=auth(first["token"])).json() == []
    assert len(api.get("/api/jobs", headers=auth(second["token"])).json()) == 1


# ---------------------------------------------------------------------
# Approval atomicity
# ---------------------------------------------------------------------


def test_approving_twice_returns_the_same_token(api, two_accounts):
    """Idempotent by construction, not by luck.

    The old read-then-insert-then-update sequence could interleave on a
    double click: both calls saw no interview, both inserted, and the loser
    hit the interviews.candidate_id unique constraint and surfaced as a
    500. Re-issuing a token would also break a link HR had already sent.
    """
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]

    first = api.post(f"/api/candidates/{candidate_id}/approve", headers=a)
    second = api.post(f"/api/candidates/{candidate_id}/approve", headers=a)

    assert first.status_code == second.status_code == 200
    assert first.json()["interview_token"] == second.json()["interview_token"]
    assert first.json()["state"] == "approved"


def test_approving_does_not_reopen_a_finished_interview(api, two_accounts):
    """A candidate who has already been interviewed stays interviewed. The
    state machine only moves forward here."""
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]

    api.post(f"/api/candidates/{candidate_id}/approve", headers=a)
    storage.set_candidate_state(candidate_id, "interviewed")

    again = api.post(f"/api/candidates/{candidate_id}/approve", headers=a)
    assert again.json()["state"] == "interviewed"


# ---------------------------------------------------------------------
# The final decision. Two terminal states, and neither one reverses the
# other. database/004_hired_state.sql.
# ---------------------------------------------------------------------


def test_hiring_records_the_one_terminal_state_that_is_not_rejection(api, two_accounts):
    """Before this the pipeline could only end badly: 'rejected' was the
    only terminal state, so a finished search and one still waiting on a
    decision looked the same."""
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]
    storage.set_candidate_state(candidate_id, "interviewed")

    hired = api.post(f"/api/candidates/{candidate_id}/hire", headers=a)
    assert hired.status_code == 200
    assert hired.json()["state"] == "hired"

    # Idempotent: a second click is not an error.
    again = api.post(f"/api/candidates/{candidate_id}/hire", headers=a)
    assert again.status_code == 200
    assert again.json()["state"] == "hired"

    # And it survives a reload, because it is a row and not a piece of
    # frontend state.
    reloaded = api.get(f"/api/candidates/{candidate_id}", headers=a)
    assert reloaded.json()["state"] == "hired"


def test_hiring_is_not_a_way_to_reverse_a_rejection(api, two_accounts):
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]
    api.post(f"/api/candidates/{candidate_id}/reject", headers=a)

    response = api.post(f"/api/candidates/{candidate_id}/hire", headers=a)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "candidate_already_decided"
    assert storage.get_candidate(candidate_id)["state"] == "rejected"


def test_rejecting_is_not_a_way_to_reverse_a_hire(api, two_accounts):
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]
    storage.set_candidate_state(candidate_id, "interviewed")
    api.post(f"/api/candidates/{candidate_id}/hire", headers=a)

    response = api.post(f"/api/candidates/{candidate_id}/reject", headers=a)
    assert response.status_code == 409
    assert storage.get_candidate(candidate_id)["state"] == "hired"


def test_approving_does_not_walk_a_hired_candidate_backwards(api, two_accounts):
    """Same rule the SQL function carries: a candidate already further
    along is left where they are."""
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]
    api.post(f"/api/candidates/{candidate_id}/approve", headers=a)
    storage.set_candidate_state(candidate_id, "hired")

    again = api.post(f"/api/candidates/{candidate_id}/approve", headers=a)
    assert again.json()["state"] == "hired"


def test_hiring_against_a_database_without_the_migration_says_so(
    api, two_accounts, monkeypatch
):
    """The one route that can outrun its own database. A raw check-constraint
    violation is a 500 nobody can read during a demo."""
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]
    storage.set_candidate_state(candidate_id, "interviewed")

    def refuse(*_args, **_kwargs):
        raise RuntimeError(
            '{"code":"23514","message":"new row for relation \\"candidates\\" '
            'violates check constraint \\"candidates_state_check\\""}'
        )

    monkeypatch.setattr(storage, "set_candidate_state", refuse)
    response = api.post(f"/api/candidates/{candidate_id}/hire", headers=a)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "schema_out_of_date"
    assert "004_hired_state.sql" in response.json()["error"]["message"]


def test_a_hired_candidate_is_told_the_outcome_and_no_more(api, two_accounts):
    """The candidate portal rule holds for the good outcome too: they are
    told where they stand, never a number and never any terms."""
    a = auth(two_accounts["a"]["token"])
    candidate_id = two_accounts["candidate"]["id"]
    storage.set_candidate_state(candidate_id, "interviewed")
    api.post(f"/api/candidates/{candidate_id}/hire", headers=a)

    email = storage.get_candidate(candidate_id)["email"]
    rows = api.get("/api/applications", params={"email": email}).json()
    assert rows[0]["status"] == "offer"
    assert rows[0]["status_label"] == "Offer"
    assert "score" not in rows[0]["status_detail"].lower()


# ---------------------------------------------------------------------
# DEMO_AUTH. A real bypass, so it gets real tests.
# ---------------------------------------------------------------------


@pytest.fixture
def demo_auth(monkeypatch):
    """Turn the bypass on for one test.

    The autouse fixture in conftest pins it off everywhere else, so the
    real auth path is what the rest of this file exercises.
    """
    from app.core.config import get_settings

    monkeypatch.setenv("DEMO_AUTH", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_demo_auth_lets_any_password_in(api, store, demo_auth):
    first = api.post(
        "/api/auth/login", json={"email": "anyone@example.com", "password": "a"}
    )
    assert first.status_code == 200

    # A different password, same account: the password is not consulted.
    second = api.post(
        "/api/auth/login",
        json={"email": "anyone@example.com", "password": "something-else-entirely"},
    )
    assert second.status_code == 200
    assert second.json()["account"]["id"] == first.json()["account"]["id"]


def test_demo_auth_creates_the_account_once_not_per_attempt(api, store, demo_auth):
    """Otherwise a demo accumulates a workspace per sign in and the jobs
    stay behind with the first one."""
    for _ in range(3):
        api.post("/api/auth/login", json={"email": "repeat@example.com", "password": "x"})

    users = store.snapshot()["hr_users"]
    assert len(users) == 1


def test_demo_auth_still_issues_a_real_session(api, store, demo_auth):
    """The bypass changes who may sign in, not how sessions work. A route
    still refuses a caller with no token."""
    token = api.post(
        "/api/auth/login", json={"email": "anyone@example.com", "password": "x"}
    ).json()["token"]

    assert api.get("/api/jobs").status_code == 401
    assert api.get("/api/jobs", headers=auth(token)).status_code == 200


def test_demo_auth_still_scopes_jobs_to_the_account(api, store, demo_auth):
    """Signing in as anyone does not mean seeing everyone's data. Ownership
    is a separate rule and it still holds."""
    a = api.post("/api/auth/login", json={"email": "a@example.com", "password": "x"}).json()
    b = api.post("/api/auth/login", json={"email": "b@example.com", "password": "x"}).json()

    storage.create_job("A's role", "d" * 200, ["SQL"], None, owner_id=a["account"]["id"])

    assert len(api.get("/api/jobs", headers=auth(a["token"])).json()) == 1
    assert api.get("/api/jobs", headers=auth(b["token"])).json() == []


def test_demo_auth_off_by_default_refuses_a_wrong_password(api, store):
    """The guard on the guard. If the conftest fixture ever stops pinning
    DEMO_AUTH off, this fails rather than the whole suite passing by
    accident."""
    register(api, "real@example.com")
    response = api.post(
        "/api/auth/login", json={"email": "real@example.com", "password": "wrong"}
    )
    assert response.status_code == 401

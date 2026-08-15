"""DEMO_MODE must work with no network at all.

Implementation plan 10.3: "DEMO_MODE=1 verified with the network
physically disconnected. A cassette miss raises loudly rather than calling
out." This is the phase's done-when condition, and the only one that
cannot be fixed live during a demo.

Rather than ask a human to pull the cable, these tests make the network
genuinely unreachable inside the process: `socket.socket` is replaced with
one that raises on construction. Nothing can dial out - not Gemini, not
Groq, not Supabase, not a stray HTTP client somewhere in a dependency - and
any attempt fails the test loudly with the offending call in the traceback.

That is a stronger guarantee than an unplugged cable, because an unplugged
cable produces a timeout that some code path might quietly swallow and
retry, while this produces an immediate, attributable error.
"""

from __future__ import annotations

import json
import socket

import pytest

from app import cassettes
from app.core.config import Settings, get_settings
from app.integrations import storage
from app.integrations.demo_supabase import DemoClient


class NetworkUsed(AssertionError):
    """Raised the moment anything tries to open a socket."""


@pytest.fixture
def offline(monkeypatch):
    """Make outbound networking impossible for the duration of a test.

    Only the IP families are blocked. AF_UNIX socket pairs are local
    process plumbing - anyio, which FastAPI's TestClient runs on, builds
    one to talk to its own event loop - and they cannot reach a network by
    construction. Blocking those would fail the test for a reason that has
    nothing to do with a demo machine being offline.
    """
    real_socket = socket.socket

    def forbidden(family=socket.AF_INET, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            raise NetworkUsed(
                "DEMO_MODE attempted to open a network connection. Everything "
                "in demo mode must be served from tests/cassettes/."
            )
        return real_socket(family, *args, **kwargs)

    def forbidden_connection(*args, **kwargs):
        raise NetworkUsed("DEMO_MODE attempted an outbound connection.")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden_connection)
    # getaddrinfo is what most clients hit first; failing here names the
    # host that was about to be contacted.
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, *a, **k: (_ for _ in ()).throw(
            NetworkUsed(f"DEMO_MODE tried to resolve {host!r}")
        ),
    )
    return forbidden


@pytest.fixture
def demo(monkeypatch, tmp_path):
    """Turn DEMO_MODE on with an isolated, populated cassette directory."""
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: Settings(demo_mode=True, supabase_url="", supabase_service_role_key=""),
    )
    # Every module that reads settings imported the function directly.
    for module in ("app.cassettes", "app.integrations.llm", "app.integrations.stt",
                   "app.integrations.storage"):
        monkeypatch.setattr(f"{module}.get_settings", lambda: Settings(demo_mode=True))

    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)
    storage.get_client.cache_clear()
    yield tmp_path
    storage.get_client.cache_clear()
    get_settings.cache_clear()


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload))


# --- The offline guard itself ----------------------------------------------


def test_the_offline_guard_actually_blocks_the_network(offline):
    """If this passes trivially, every other test in this file is
    meaningless. Prove the guard bites before trusting it."""
    with pytest.raises(NetworkUsed):
        socket.socket()
    with pytest.raises(NetworkUsed):
        socket.getaddrinfo("generativelanguage.googleapis.com", 443)


# --- Replay ----------------------------------------------------------------


def test_gemini_replays_offline(offline, demo):
    from app.integrations import llm
    from app.models import Rubric
    from tests.fixtures.rubrics import valid_rubric

    rubric = valid_rubric()
    system, user = "sys", "usr"
    _write(
        demo,
        cassettes.GEMINI_FILE,
        {
            cassettes.gemini_key(system, user, "Rubric"): {
                "stage": "Rubric",
                "response": rubric.model_dump(mode="json"),
            }
        },
    )

    result = llm.generate_structured(system, user, Rubric)

    assert isinstance(result, Rubric)
    assert sum(c.points for c in result.criteria) == 100


def test_transcription_replays_offline(offline, demo):
    from app.integrations.stt import transcribe

    audio = b"\x1aE\xdf\xa3" + b"golden" * 200
    _write(
        demo,
        cassettes.STT_FILE,
        {cassettes.audio_key(audio): {"bytes": len(audio), "transcript": "Hi, I am Priya."}},
    )

    assert transcribe(audio, "introduction.webm") == "Hi, I am Priya."


def test_storage_reads_and_writes_offline(offline, demo):
    """The whole storage module runs for real against the in-memory store,
    including ordering and the unique constraint."""
    _write(
        demo,
        cassettes.SUPABASE_FILE,
        {
            "jobs": [
                {
                    "id": "job-1",
                    "title": "Senior Python Developer",
                    "description": "d",
                    "skills": ["Python"],
                    "state": "active",
                    "rubric": {"criteria": [], "interview_topics": []},
                    "created_at": "2026-08-14T00:00:00+00:00",
                }
            ]
        },
    )

    assert storage.get_job("job-1")["title"] == "Senior Python Developer"
    assert len(storage.list_jobs()) == 1

    created = storage.create_candidate(
        job_id="job-1",
        name="Priya Nair",
        email="priya@example.com",
        resume_path=None,
        resume_text="r",
        audio_path=None,
        transcript="t",
    )
    assert storage.get_candidate(created["id"])["name"] == "Priya Nair"

    # The unique constraint is enforced by the fake exactly as Postgres
    # would, so /apply still returns `already_applied` in a demo.
    from app.core.errors import AlreadyApplied

    with pytest.raises(AlreadyApplied):
        storage.create_candidate(
            job_id="job-1",
            name="Priya Again",
            email="priya@example.com",
            resume_path=None,
            resume_text="r",
            audio_path=None,
            transcript="t",
        )


def test_ranked_list_sorts_nulls_last_offline(offline, demo):
    """A candidate mid-screening has no score and must sort last, not
    first, or the demo dashboard leads with an unscored row."""
    _write(demo, cassettes.SUPABASE_FILE, {})
    client = DemoClient()

    for name, score in (("Mid", None), ("High", 84), ("Low", 41)):
        client.table("candidates").insert(
            {
                "id": name,
                "job_id": "job-1",
                "name": name,
                "email": f"{name}@example.com",
                "screening_score": score,
            }
        ).execute()

    rows = (
        client.table("candidates")
        .select("*")
        .eq("job_id", "job-1")
        .order("screening_score", desc=True, nullsfirst=False)
        .execute()
        .data
    )
    assert [r["name"] for r in rows] == ["High", "Low", "Mid"]


def test_two_candidates_without_an_email_are_not_duplicates(demo):
    """Postgres unique constraints ignore nulls. The fake must too, or a
    demo behaves differently from the real database on a real edge."""
    client = DemoClient()
    for i in (1, 2):
        client.table("candidates").insert(
            {"job_id": "job-1", "name": f"Anon {i}", "email": None}
        ).execute()
    assert len(client.table("candidates").select("*").execute().data) == 2


# --- A miss must be loud ---------------------------------------------------


def test_gemini_cassette_miss_raises_and_does_not_call_out(offline, demo):
    from app.integrations import llm
    from app.models import Rubric

    _write(demo, cassettes.GEMINI_FILE, {})

    # The failure is a CassetteMiss, not a connection error: proof the code
    # stopped at the cassette rather than trying the network and failing.
    with pytest.raises(cassettes.CassetteMiss) as caught:
        llm.generate_structured("sys", "unrecorded prompt", Rubric)

    assert "record" in str(caught.value).lower()


def test_stt_cassette_miss_raises_and_does_not_call_out(offline, demo):
    from app.integrations.stt import transcribe

    _write(demo, cassettes.STT_FILE, {})

    with pytest.raises(cassettes.CassetteMiss):
        transcribe(b"\x1aE\xdf\xa3" + b"unrecorded", "answer.webm")


def test_a_prompt_edit_misses_rather_than_replaying_the_wrong_answer(offline, demo):
    """The property that makes cassettes safe to keep around.

    Keys include a hash of the exact prompt, so editing a prompt and
    forgetting to re-record produces a loud miss instead of silently
    serving the answer to the question that used to be asked.
    """
    from app.integrations import llm
    from app.models import Rubric
    from tests.fixtures.rubrics import valid_rubric

    _write(
        demo,
        cassettes.GEMINI_FILE,
        {
            cassettes.gemini_key("sys", "the original prompt", "Rubric"): {
                "stage": "Rubric",
                "response": valid_rubric().model_dump(mode="json"),
            }
        },
    )

    assert llm.generate_structured("sys", "the original prompt", Rubric)

    with pytest.raises(cassettes.CassetteMiss):
        llm.generate_structured("sys", "the prompt after an edit", Rubric)


def test_oversized_audio_still_rejected_in_demo_mode(offline, demo):
    """Errors that are properties of the file, not the provider, behave
    identically offline. A demo should reject a 30MB upload the way the
    live system does."""
    from app.core.errors import AudioTooLarge
    from app.core.heuristics import AUDIO_MAX_BYTES
    from app.integrations.stt import transcribe

    _write(demo, cassettes.STT_FILE, {})

    with pytest.raises(AudioTooLarge):
        transcribe(b"0" * (AUDIO_MAX_BYTES + 1), "answer.webm")


# --- The real committed cassettes, replayed offline -------------------------


@pytest.fixture
def demo_real(monkeypatch):
    """DEMO_MODE against the cassettes that are actually committed.

    Everything above this point uses hand-written fixtures, which proves
    the mechanism. This proves the artefact: the files a demo machine will
    actually ship with, replayed through the real HTTP API with the
    network unreachable.
    """
    get_settings.cache_clear()
    for module in (
        "app.cassettes",
        "app.integrations.llm",
        "app.integrations.stt",
        "app.integrations.storage",
    ):
        monkeypatch.setattr(f"{module}.get_settings", lambda: Settings(demo_mode=True))
    storage.get_client.cache_clear()
    yield
    storage.get_client.cache_clear()
    get_settings.cache_clear()


@pytest.mark.skipif(
    not (cassettes.CASSETTE_DIR / cassettes.SUPABASE_FILE).exists(),
    reason="cassettes not recorded yet; run python -m tests.record_cassettes",
)
def test_the_whole_demo_flow_serves_offline_from_real_cassettes(offline, demo_real):
    """The demo walk-through, over HTTP, with no network.

    This is implementation-plan 10.3. If this passes, a laptop in
    aeroplane mode with no API keys can still run the client demo.
    """
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())

    # Register the demo account. The cassette rows predate accounts and
    # therefore have no owner, so this is also the first-account claim
    # running for real: if it did not work, every assertion below would
    # come back empty. That is the whole reason the claim happens inside
    # the register transaction rather than as a second call.
    session = client.post(
        "/api/auth/register",
        json={
            "email": "demo@rubric.test",
            "name": "Demo Recruiter",
            "password": "demo-password-1",
        },
    )
    assert session.status_code == 200, session.text
    assert session.json()["claimed_jobs"] >= 1
    client.headers["Authorization"] = f"Bearer {session.json()['token']}"

    jobs = client.get("/api/jobs").json()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["state"] == "active"
    assert job["applicant_count"] == 1

    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert sum(c["points"] for c in detail["rubric"]["criteria"]) == 100

    candidates = client.get(f"/api/jobs/{job['id']}/candidates").json()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["screening_score"] is not None
    assert candidate["screening_band"] in ("strong", "borderline", "weak")

    full = client.get(f"/api/candidates/{candidate['id']}").json()
    # The sub-scores sum to the reported total. The invariant CLAUDE.md is
    # built around, checked on the row a demo actually renders.
    assert sum(s["points_awarded"] for s in full["sub_scores"]) == full["screening_score"]
    assert full["interview_token"]

    result = client.get(f"/api/candidates/{candidate['id']}/interview").json()
    assert result["status"] == "evaluated"
    assert result["overall_score"] is not None
    assert len(result["turns"]) == 7
    assert all(turn["answer_text"] for turn in result["turns"])

    # The candidate-facing side of the same interview link.
    session = client.get(f"/api/interview/{full['interview_token']}").json()
    assert session["status"] == "evaluated"
    assert session["job_title"] == job["title"]


@pytest.mark.skipif(
    not (cassettes.CASSETTE_DIR / cassettes.GEMINI_FILE).exists(),
    reason="cassettes not recorded yet",
)
def test_every_recorded_stage_is_present(demo_real):
    """A cassette set missing a stage fails somewhere in the middle of a
    live demo. Fail here instead, where it is cheap."""
    import json

    recorded = json.loads((cassettes.CASSETTE_DIR / cassettes.GEMINI_FILE).read_text())
    stages = {entry["stage"] for entry in recorded.values()}
    for required in ("Rubric", "Screening", "InterviewPlan", "TurnResult", "Evaluation"):
        assert required in stages, f"no {required} cassette recorded"

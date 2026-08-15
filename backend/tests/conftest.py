import pytest
from fastapi.testclient import TestClient

from app.core.auth import HRUser, require_hr
from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def real_auth(monkeypatch):
    """Every test runs against real authentication.

    DEMO_AUTH is a genuine bypass and a developer may well have it set in
    their local .env, which pydantic-settings reads. Without this the whole
    auth suite would quietly pass by taking the bypass, and the tests that
    matter most here would be testing nothing.

    The bypass has its own tests, which turn it on explicitly.
    """
    monkeypatch.setenv("DEMO_AUTH", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

# The account every route test runs as. Its id is what the mocked job rows
# in the route tests carry as `owner_id`, so ownership resolves the same
# way it does against a real database.
HR_TEST_USER = HRUser(
    id="hr-test-1",
    email="hr@example.com",
    name="Test Recruiter",
    company="Example",
)


@pytest.fixture
def client() -> TestClient:
    """Signed in as HR_TEST_USER.

    Most route tests are about the route contract, not about the session
    check, so the dependency is overridden rather than driven through a
    real login on every test. The session check itself, and every
    ownership boundary, is tested for real in tests/test_auth.py against
    the `anon_client` fixture below.
    """
    app = create_app()
    app.dependency_overrides[require_hr] = lambda: HR_TEST_USER
    return TestClient(app)


@pytest.fixture
def anon_client() -> TestClient:
    """No session. Used to prove the HR routes actually refuse one."""
    return TestClient(create_app())

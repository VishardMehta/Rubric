"""Session enforcement for the HR routes.

A FastAPI dependency, deliberately not middleware. Middleware would have to
carry a list of public paths, and the candidate side of this product is
entirely public: apply, the opportunity list, every interview route, and
health. A typo in that allowlist either locks a candidate out of their
interview or opens HR's data to the internet, and neither failure is
visible by reading the route it affects.

As a dependency the rule is local and legible: a route that declares
`hr: HRUser = Depends(require_hr)` is protected, and one that does not is
public, which you can see while looking straight at it.

Transport is `Authorization: Bearer <token>`, not a cookie. CORS is
configured with `allow_credentials=False` and pinned origins
(core/config.py), so a cookie would not be sent cross-origin without
loosening that. The token lives in the browser's localStorage, which is
readable by any script that gets injected into the page. For a localhost
demo with no third-party scripts that is an acceptable trade, and it is
written down in the README rather than left implicit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Header

from app.core.errors import NotAuthenticated
from app.integrations import storage

logger = logging.getLogger("rubric.auth")


@dataclass(frozen=True)
class HRUser:
    """The signed-in account. Frozen so a route cannot accidentally mutate
    the identity it was handed and have that leak into a later call."""

    id: str
    email: str
    name: str
    company: str | None


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def require_hr(authorization: str | None = Header(default=None)) -> HRUser:
    """Resolve the bearer token to an account, or raise 401.

    An expired session is deleted rather than merely rejected, so the row
    does not sit there forever. There is no sliding renewal: the session
    lasts SESSION_TTL_HOURS from issue and then requires a fresh sign in.
    """
    token = _bearer(authorization)
    if token is None:
        raise NotAuthenticated()

    session = storage.get_session(token)
    if session is None:
        raise NotAuthenticated()

    expires_at = session.get("expires_at")
    if _has_expired(expires_at):
        storage.delete_session(token)
        raise NotAuthenticated("Your session has expired. Sign in again.")

    user = storage.get_hr_user(session["hr_user_id"])
    if user is None:
        # The account was deleted while the session was live. Treat it as
        # signed out rather than 500ing on a missing row.
        storage.delete_session(token)
        raise NotAuthenticated()

    return HRUser(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        company=user.get("company"),
    )


def _has_expired(expires_at: str | None) -> bool:
    """Postgres returns an ISO timestamp; the in-memory demo store returns
    the same shape. A value that cannot be parsed is treated as expired,
    because the safe reading of "I cannot tell when this ends" is "now".

    fromisoformat handles a trailing Z natively from Python 3.11, which is
    the floor in pyproject.toml.
    """
    if not expires_at:
        return True
    try:
        parsed = datetime.fromisoformat(expires_at)
    except ValueError:
        logger.warning("unparseable session expiry, treating as expired")
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed <= datetime.now(UTC)

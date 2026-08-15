"""HR account routes.

Registration is open. This is a localhost demo with no email delivery, so
there is no invitation flow and nobody to approve a signup. That is a
deliberate limit, recorded in the README next to the other stated ones,
not an oversight.

There is no password reset for the same reason: a reset needs somewhere to
send a link, and email is out of scope (product.md section 7).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header

from app.core.auth import HRUser, require_hr
from app.core.config import get_settings
from app.core.errors import InvalidCredentials, WeakPassword
from app.core.heuristics import PASSWORD_MIN_LENGTH, SESSION_TTL_HOURS
from app.integrations import storage
from app.models import (
    HRAccount,
    LoginRequest,
    RegisterRequest,
    SessionResponse,
)
from app.services.accounts import (
    hash_password,
    new_session_token,
    normalise_email,
    verify_password,
)

logger = logging.getLogger("rubric.api.auth")

router = APIRouter(tags=["auth"])


def _issue_session(user_id: str, account: HRAccount, claimed_jobs: int = 0) -> SessionResponse:
    token = new_session_token()
    expires_at = (datetime.now(UTC) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
    storage.create_session(token, user_id, expires_at)
    return SessionResponse(
        token=token,
        expires_at=expires_at,
        account=account,
        claimed_jobs=claimed_jobs,
    )


def _demo_sign_in(email: str, name: str | None = None) -> SessionResponse:
    """Sign in as whoever was typed, creating the account if needed.

    Only reachable when settings.demo_auth is on. The password is not
    checked at all, so this is a genuine authentication bypass and is
    logged as one every time it is used.

    Existing accounts are reused rather than duplicated, so a demo run does
    not accumulate a new workspace per attempt and the jobs stay where they
    were.
    """
    normalised = normalise_email(email)
    logger.warning(
        "DEMO_AUTH: signing in as %s without checking a password", normalised
    )

    user = storage.get_hr_user_by_email(normalised)
    claimed = 0
    if user is None:
        password_hash, password_salt = hash_password(new_session_token())
        created = storage.create_hr_user(
            email=normalised,
            name=(name or "").strip() or normalised.split("@")[0].replace(".", " ").title(),
            company=None,
            password_hash=password_hash,
            password_salt=password_salt,
        )
        claimed = int(created.get("claimed_jobs") or 0)
        user = storage.get_hr_user_by_email(normalised)

    assert user is not None  # just created it above if it was missing
    account = HRAccount(
        id=user["id"], email=user["email"], name=user["name"], company=user.get("company")
    )
    return _issue_session(user["id"], account, claimed)


@router.post("/auth/register", response_model=SessionResponse)
async def register(payload: RegisterRequest) -> SessionResponse:
    """Create an account and sign straight in.

    The first account claims every job that has no owner, which is what
    keeps the rows created before accounts existed (including everything
    from database/seed.sql) reachable. That claim happens inside the same
    transaction as the insert.
    """
    if get_settings().demo_auth:
        return _demo_sign_in(payload.email, payload.name)

    if len(payload.password) < PASSWORD_MIN_LENGTH:
        raise WeakPassword(
            f"Use at least {PASSWORD_MIN_LENGTH} characters. Length is what makes a "
            "password hard to guess."
        )
    if not payload.name.strip():
        raise WeakPassword("Enter your name.")

    password_hash, password_salt = hash_password(payload.password)
    # Raises EmailAlreadyRegistered on the unique constraint.
    created = storage.create_hr_user(
        email=normalise_email(payload.email),
        name=payload.name.strip(),
        company=(payload.company or "").strip() or None,
        password_hash=password_hash,
        password_salt=password_salt,
    )

    claimed = int(created.get("claimed_jobs") or 0)
    if claimed:
        logger.info("first account claimed %d ownerless job(s)", claimed)

    account = HRAccount(
        id=created["id"],
        email=created["email"],
        name=created["name"],
        company=created.get("company"),
    )
    return _issue_session(created["id"], account, claimed)


@router.post("/auth/login", response_model=SessionResponse)
async def login(payload: LoginRequest) -> SessionResponse:
    if get_settings().demo_auth:
        return _demo_sign_in(payload.email)

    user = storage.get_hr_user_by_email(normalise_email(payload.email))

    # Same error whether the account is missing or the password is wrong,
    # so the response cannot be used to enumerate registered addresses.
    if user is None or not verify_password(
        payload.password, user["password_hash"], user["password_salt"]
    ):
        raise InvalidCredentials()

    account = HRAccount(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        company=user.get("company"),
    )
    return _issue_session(user["id"], account)


@router.post("/auth/logout")
async def logout(authorization: str | None = Header(default=None)) -> dict:
    """Delete the session row.

    Deliberately does not use require_hr: signing out with an already
    expired token should succeed quietly rather than fail with a 401 and
    leave the frontend unsure whether it is signed out.
    """
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            storage.delete_session(token.strip())
    return {"status": "signed_out"}


@router.get("/auth/me", response_model=HRAccount)
async def me(hr: HRUser = Depends(require_hr)) -> HRAccount:
    """Who the current token belongs to. The frontend calls this on load to
    decide whether a stored token is still good."""
    return HRAccount(id=hr.id, email=hr.email, name=hr.name, company=hr.company)

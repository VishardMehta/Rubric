"""Password hashing and session tokens for HR accounts.

No new dependency. CLAUDE.md forbids adding one without asking, and the
standard library already has everything needed: `hashlib.scrypt` for a
memory-hard KDF, `secrets` for tokens and salts, `hmac.compare_digest` for
constant-time comparison.

`pyjwt` is installed in the venv, but only because `supabase` pulls it in.
It is not in pyproject.toml, so using it would mean depending on another
package's transitive dependency. Sessions are opaque random tokens in a
table instead, which is also the only way to revoke one.

What is deliberately NOT here: any password policy beyond a length floor,
any "security question", any reset flow. This is a localhost demo with no
email delivery (product.md section 7), so a reset flow would have nowhere
to send anything.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.heuristics import (
    PASSWORD_SALT_BYTES,
    PASSWORD_SCRYPT_DKLEN,
    PASSWORD_SCRYPT_MAXMEM,
    PASSWORD_SCRYPT_N,
    PASSWORD_SCRYPT_P,
    PASSWORD_SCRYPT_R,
)


def _derive(password: str, salt: bytes) -> str:
    """scrypt the password with the pinned cost parameters, hex encoded."""
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_SCRYPT_DKLEN,
        maxmem=PASSWORD_SCRYPT_MAXMEM,
    ).hex()


def hash_password(password: str) -> tuple[str, str]:
    """Return (hash, salt), both hex. A fresh salt per account, so two
    people choosing the same password do not end up with the same hash."""
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    return _derive(password, salt), salt.hex()


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    """Constant-time check.

    `compare_digest` rather than `==` so the comparison does not leak how
    many leading characters matched. A malformed salt is treated as a
    failed login rather than an exception: a corrupt row should not be
    distinguishable from a wrong password.
    """
    try:
        salt = bytes.fromhex(password_salt)
    except ValueError:
        return False
    return hmac.compare_digest(_derive(password, salt), password_hash)


def new_session_token() -> str:
    """256 bits of entropy, same construction as the interview token.

    This is a bearer credential: whoever holds it is the HR user until it
    expires, so it is never derived from the email or the user id.
    """
    return secrets.token_urlsafe(32)


def normalise_email(email: str) -> str:
    """Lowercased and trimmed.

    Applied on both registration and login so that a capitalised address
    reaches the same row. The database stores the normalised form, and the
    unique constraint is therefore on the normalised value.
    """
    return email.strip().lower()

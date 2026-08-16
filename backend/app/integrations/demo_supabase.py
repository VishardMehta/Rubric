"""An in-memory stand-in for the Supabase client, used only in DEMO_MODE.

Why this exists
---------------
CLAUDE.md: "Cache the Supabase rows for that candidate too, since Supabase
makes the internet a hard dependency." A free Supabase project also pauses
after about seven days idle, so the database is the single most likely
thing to be down at demo time, and it is down in a way that looks exactly
like a broken application.

Why it fakes the client rather than the storage functions
---------------------------------------------------------
`storage.get_client()` is the only seam every one of the ~30 storage
functions passes through. Replacing the client leaves all of that code
running for real - the same queries, the same row shapes, the same
ordering, the same unique-constraint handling - which means DEMO_MODE
exercises the actual storage layer instead of bypassing it. A per-function
replay would have skipped the code most likely to break.

This is a demo fixture, not a database. It implements exactly the slice of
the PostgREST fluent API that storage.py uses, and nothing else. An
unsupported call raises rather than quietly returning nothing.
"""

from __future__ import annotations

import copy
import re
import uuid
from datetime import UTC, datetime
from typing import Any

# Column defaults that Postgres would apply on insert. Kept in sync with
# database/schema.sql by hand; the demo-mode test asserts on the states
# these produce, so a drift here fails a test rather than a demo.
_DEFAULTS: dict[str, dict[str, Any]] = {
    "jobs": {
        "skills": [],
        "state": "analyzing",
        "rubric": None,
        "experience": None,
        # database/002_accounts.sql. Nullable, so a job seeded before
        # accounts existed still inserts here exactly as it does in
        # Postgres.
        "owner_id": None,
        "employment_type": None,
        "workplace_type": None,
        "location": None,
        "department": None,
        "compensation": None,
    },
    "hr_users": {"company": None},
    "hr_sessions": {},
    "candidates": {
        "matched_skills": [],
        "unevidenced_skills": [],
        "resume_intro_conflicts": [],
        "state": "applied",
        "screening_score": None,
        "screening_band": None,
        "sub_scores": None,
        "voice_sub_scores": None,
        "resume_score": None,
        "voice_score": None,
        "assessment": None,
        "recommendation": None,
        "resume_profile": None,
    },
    "interviews": {
        "state_object": {},
        "status": "not_started",
        "plan": None,
        "total_questions": None,
        "started_at": None,
        "completed_at": None,
        "invited_at": None,
    },
    "interview_turns": {
        "criterion_ids": [],
        "answer_text": None,
        "answer_audio_path": None,
        "answer_scores": None,
        "response_time_seconds": None,
        "answered_at": None,
    },
    "interview_results": {"strengths": [], "concerns": []},
}

# Tables whose primary key is not `id`. interview_results is keyed on the
# interview it belongs to, which is what makes its upsert idempotent.
_PRIMARY_KEY = {"interview_results": "interview_id", "hr_sessions": "token"}

# Unique constraints that the application depends on catching. The message
# carries 23505 so storage._is_unique_violation recognises it exactly as it
# would a real PostgREST error.
_UNIQUE: dict[str, tuple[str, ...]] = {
    "candidates": ("job_id", "email"),
    "interviews": ("candidate_id",),
    "hr_users": ("email",),
}


class UnsupportedQuery(RuntimeError):
    """A query shape the demo store does not implement.

    Raised loudly and never swallowed: silently returning an empty result
    would show an empty dashboard during a demo and look like data loss.
    """


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_now(value: Any) -> Any:
    """Postgres evaluates the literal `now()` we send for timestamps."""
    return _now() if value == "now()" else value


class _Result:
    __slots__ = ("data",)

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    """One table query. Filters accumulate, `execute` applies them."""

    def __init__(self, store: dict[str, list[dict[str, Any]]], table: str) -> None:
        self._store = store
        self._table = table
        self._op = "select"
        self._payload: dict[str, Any] | None = None
        self._filters: list[tuple[str, str, Any]] = []
        self._order: tuple[str, bool, bool] | None = None

    # --- builders -------------------------------------------------------
    def select(self, _columns: str = "*") -> _Query:
        # Column projection is ignored on purpose. Every caller either uses
        # "*" or reads a subset of the keys it asked for, so returning the
        # whole row is a superset of what any caller reads.
        self._op = "select"
        return self

    def insert(self, payload: dict[str, Any]) -> _Query:
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> _Query:
        self._op = "update"
        self._payload = payload
        return self

    def upsert(self, payload: dict[str, Any]) -> _Query:
        self._op = "upsert"
        self._payload = payload
        return self

    def delete(self) -> _Query:
        self._op = "delete"
        return self

    def eq(self, column: str, value: Any) -> _Query:
        self._filters.append(("eq", column, value))
        return self

    def in_(self, column: str, values: list[Any]) -> _Query:
        self._filters.append(("in", column, values))
        return self

    def order(self, column: str, desc: bool = False, nullsfirst: bool = False) -> _Query:
        self._order = (column, desc, nullsfirst)
        return self

    # --- execution ------------------------------------------------------
    def _rows(self) -> list[dict[str, Any]]:
        return self._store.setdefault(self._table, [])

    def _matching(self) -> list[dict[str, Any]]:
        rows = self._rows()
        for kind, column, value in self._filters:
            if kind == "eq":
                rows = [r for r in rows if r.get(column) == value]
            elif kind == "in":
                rows = [r for r in rows if r.get(column) in value]
            else:  # pragma: no cover - only two filter kinds are built
                raise UnsupportedQuery(f"filter {kind!r}")
        return rows

    def _check_unique(self, row: dict[str, Any]) -> None:
        columns = _UNIQUE.get(self._table)
        if not columns:
            return
        # Postgres does not treat NULL as equal to NULL, so a unique
        # constraint never fires when any constrained column is null. Two
        # rows with no email are not duplicates of each other.
        if any(row.get(c) is None for c in columns):
            return
        for existing in self._rows():
            if all(existing.get(c) == row.get(c) for c in columns):
                raise RuntimeError(
                    f"duplicate key value violates unique constraint "
                    f"(23505): {self._table}({', '.join(columns)})"
                )

    def execute(self) -> _Result:
        if self._op == "select":
            rows = self._matching()
            if self._order:
                column, desc, nullsfirst = self._order
                # None sorts to whichever end the caller asked for, matching
                # `nulls last` on the ranked candidate index in schema.sql.
                missing = (not nullsfirst) != desc

                rows = sorted(
                    rows,
                    key=lambda r: (
                        (r.get(column) is None) == missing,
                        _sort_key(r.get(column)),
                    ),
                    reverse=desc,
                )
            return _Result(copy.deepcopy(rows))

        if self._op == "insert":
            row = {k: _resolve_now(v) for k, v in (self._payload or {}).items()}
            merged = {**_DEFAULTS.get(self._table, {}), **row}
            key = _PRIMARY_KEY.get(self._table, "id")
            merged.setdefault(key, str(uuid.uuid4()))
            merged.setdefault("created_at", _now())
            self._check_unique(merged)
            self._rows().append(merged)
            return _Result([copy.deepcopy(merged)])

        if self._op == "upsert":
            key = _PRIMARY_KEY.get(self._table, "id")
            row = {k: _resolve_now(v) for k, v in (self._payload or {}).items()}
            for existing in self._rows():
                if existing.get(key) == row.get(key):
                    existing.update(row)
                    return _Result([copy.deepcopy(existing)])
            merged = {**_DEFAULTS.get(self._table, {}), **row}
            merged.setdefault("created_at", _now())
            self._rows().append(merged)
            return _Result([copy.deepcopy(merged)])

        if self._op == "update":
            patch = {k: _resolve_now(v) for k, v in (self._payload or {}).items()}
            updated = self._matching()
            for row in updated:
                row.update(patch)
            return _Result(copy.deepcopy(updated))

        if self._op == "delete":
            doomed = self._matching()
            remaining = [r for r in self._rows() if r not in doomed]
            self._store[self._table] = remaining
            return _Result(copy.deepcopy(doomed))

        raise UnsupportedQuery(self._op)  # pragma: no cover


def _sort_key(value: Any) -> Any:
    """Order mixed types without raising. None is handled by the caller."""
    if value is None:
        return ""
    return value


class _Bucket:
    def __init__(self, name: str, objects: dict[str, bytes]) -> None:
        self._name = name
        self._objects = objects

    def upload(self, path: str, file: bytes, file_options: dict[str, str] | None = None) -> dict:
        self._objects[f"{self._name}/{path}"] = file
        return {"path": path}

    def create_signed_url(self, path: str, _ttl: int) -> dict:
        # A data URL rather than a fake https link. The audio player on
        # Candidate Detail is handed this directly, and a link to a host
        # that does not exist would spin during a demo. Empty audio at
        # least renders a real, inert player.
        return {"signedURL": f"data:audio/webm;base64,{_b64(self._objects.get(f'{self._name}/{path}', b''))}"}


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


class _Storage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects

    def from_(self, bucket: str) -> _Bucket:
        return _Bucket(bucket, self._objects)


class _RpcCall:
    """Mirrors the builder shape of `client.rpc(...).execute()`."""

    def __init__(self, result: Any) -> None:
        self._result = result

    def execute(self) -> _Result:
        return _Result(copy.deepcopy(self._result))


class DemoClient:
    """Quacks like `supabase.Client` for the calls storage.py makes."""

    def __init__(self, seed: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = copy.deepcopy(seed or {})
        self._objects: dict[str, bytes] = {}
        self.storage = _Storage(self._objects)

    def table(self, name: str) -> _Query:
        return _Query(self._tables, name)

    def rpc(self, fn: str, params: dict[str, Any] | None = None) -> _RpcCall:
        """Re-implement the Postgres functions in Python.

        These exist twice, here and in database/002_accounts.sql, which is
        a real duplication and the price of DEMO_MODE running the storage
        layer for real rather than stubbing it. The two must agree; the
        demo-mode tests assert on the behavior that distinguishes them, so
        a drift fails a test rather than a demo.

        The transactional guarantee is the one thing that does NOT need
        reproducing: this store is single-process and synchronous, so
        nothing can interleave here in the first place.
        """
        params = params or {}
        if fn == "register_hr_user":
            return _RpcCall(self._register_hr_user(params))
        if fn == "approve_candidate_atomic":
            return _RpcCall(self._approve_candidate_atomic(params))
        raise UnsupportedQuery(f"rpc {fn!r}")

    def _register_hr_user(self, params: dict[str, Any]) -> dict[str, Any]:
        users = self._tables.setdefault("hr_users", [])
        is_first = not users

        row = {
            "email": (params["p_email"] or "").strip().lower(),
            "name": params["p_name"],
            "company": params["p_company"],
            "password_hash": params["p_password_hash"],
            "password_salt": params["p_password_salt"],
        }
        # Goes through _Query so the unique-constraint check and the 23505
        # message are the same ones a real insert would raise.
        created = _Query(self._tables, "hr_users").insert(row).execute().data[0]

        claimed = 0
        if is_first:
            for job in self._tables.setdefault("jobs", []):
                if job.get("owner_id") is None:
                    job["owner_id"] = created["id"]
                    claimed += 1

        return {
            "id": created["id"],
            "email": created["email"],
            "name": created["name"],
            "company": created.get("company"),
            "created_at": created["created_at"],
            "claimed_jobs": claimed,
        }

    def _approve_candidate_atomic(self, params: dict[str, Any]) -> dict[str, Any]:
        candidate_id = params["p_candidate_id"]
        candidate = next(
            (c for c in self._tables.get("candidates", []) if c.get("id") == candidate_id),
            None,
        )
        if candidate is None:
            raise RuntimeError("candidate_not_found")

        interviews = self._tables.setdefault("interviews", [])
        existing = next(
            (i for i in interviews if i.get("candidate_id") == candidate_id), None
        )
        if existing is None:
            existing = (
                _Query(self._tables, "interviews")
                .insert({"candidate_id": candidate_id, "token": params["p_token"]})
                .execute()
                .data[0]
            )
            # _Query.insert returns a copy, so re-read the stored row.
            existing = next(
                i for i in self._tables["interviews"] if i.get("candidate_id") == candidate_id
            )

        state = candidate.get("state")
        if state not in ("approved", "interviewing", "interviewed"):
            candidate["state"] = "approved"
            state = "approved"

        return {"token": existing["token"], "state": state}

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Every row, for recording a seed file."""
        return copy.deepcopy(self._tables)


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)


def looks_like_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value or ""))

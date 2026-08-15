"""App factory: CORS, error handlers, router mounting.

Fully synchronous by design - see backend.md section 1. No task queue, no
background workers. Screening and evaluation hold the request open for the
duration of the underlying model calls.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import applications, apply, auth, candidates, health, interview, jobs
from app.core.config import get_settings
from app.core.errors import install_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Rubric API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Loud on every boot. An authentication bypass that starts quietly is
    # one nobody remembers is on.
    if settings.demo_auth:
        logging.getLogger("rubric").warning(
            "DEMO_AUTH is on: any email and any password will sign in, and the "
            "candidate portal falls back to showing every application. Never "
            "run this way outside a demo."
        )

    install_error_handlers(app)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(apply.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(candidates.router, prefix="/api")
    app.include_router(interview.router, prefix="/api")

    return app


app = create_app()

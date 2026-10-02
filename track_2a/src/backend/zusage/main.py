"""Zusage API - application entry point.

One container serves everything: the JSON API under ``/api/*`` and the built
React app for every other route. Runs on a school server, a canton's
on-premise cluster, or air-gapped next to a local Apertus - no external call
is made at runtime except to the configured ``LLM_BASE_URL``.
"""

from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, col, select

from . import __version__
from .api import auth, classes, harness, interviews, journey, workspace
from .config import Settings, get_settings
from .db import Interview, make_engine, utcnow
from .engine.brain import build_brain
from .engine.graph import build_turn_graph
from .knowledge import load_knowledge

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("zusage")


def _resolve_secret(settings: Settings) -> None:
    """Sessions must survive restarts: persist a generated secret next to the DB."""
    import os

    if os.environ.get("ZUSAGE_SECRET_KEY"):
        return
    if settings.database_url.startswith("sqlite:///") and not settings.database_url.endswith(":memory:"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        key_file = db_path.parent / ".zusage_secret"
        try:
            if key_file.exists():
                settings.secret_key = key_file.read_text().strip()
            else:
                key_file.parent.mkdir(parents=True, exist_ok=True)
                key_file.write_text(secrets.token_urlsafe(32))
                key_file.chmod(0o600)
                settings.secret_key = key_file.read_text().strip()
        except OSError:
            log.warning("could not persist session secret; sessions reset on restart")


def _purge_old_transcripts(engine, days: int) -> None:
    """Data minimisation: drop answer texts older than the retention window;
    scores and reports (needed for progress) are kept."""
    cutoff = utcnow() - timedelta(days=days)
    with Session(engine) as session:
        old = session.exec(select(Interview).where(col(Interview.created_at) < cutoff)).all()
        for iv in old:
            state = deepcopy(iv.state or {})
            if not state.get("purged"):
                state["turns"] = [{**t, "answer": "", "bridge": ""} for t in state.get("turns", [])]
                state.pop("prev", None)
                state["last_feedback"] = None
                state.pop("setup", None)
                state["interviewer_message"] = ""
                for turn in state["turns"]:
                    turn.pop("previous", None)
                    turn["assessment"] = {"scores": turn.get("assessment", {}).get("scores", {})}
                if iv.report:
                    report = deepcopy(iv.report)
                    report["narrative"] = {}
                    iv.report = report
                    state["report"] = report
                if iv.status == "active":
                    iv.status = "abandoned"
                state["purged"] = True
                iv.state = state
                session.add(iv)
        session.commit()


def _static_dir(settings: Settings) -> Path | None:
    candidates = [Path(settings.static_dir)] if settings.static_dir else []
    candidates += [Path(__file__).resolve().parents[2] / "frontend" / "dist", Path("/app/static")]
    return next((c for c in candidates if (c / "index.html").is_file()), None)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _resolve_secret(settings)
    kb = load_knowledge(settings.data_dir)
    engine = make_engine(settings.database_url)
    brain = build_brain(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.seed_demo:
            from .seed import seed_demo

            seed_demo(engine, kb, settings.data_dir)
        _purge_old_transcripts(engine, settings.transcript_retention_days)
        yield

    app = FastAPI(
        title="Zusage API",
        description="Apertus-powered interview coach for Swiss apprenticeship seekers. "
        "Every interview endpoint accepts `Authorization: Bearer <token>` for automated evaluation.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.kb = kb
    app.state.engine = engine
    app.state.brain = brain
    app.state.turn_graph = build_turn_graph(kb, brain, settings)
    app.dependency_overrides[get_settings] = lambda: settings
    log.info("coach brain: %s (%s)", brain.name, brain.model)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith(("/api/", "/v1/")):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/api/config", tags=["meta"])
    def config():
        return {
            "version": __version__,
            "mode": "live" if settings.llm_enabled else "offline",
            "model": settings.llm_name if settings.llm_enabled else brain.model,
            "demo": settings.seed_demo,
            "push_public_key": settings.push_public_key,
        }

    @app.get("/api/health", tags=["meta"])
    def health(deep: bool = False):
        out = {"status": "ok", "brain": brain.name, "model": brain.model}
        if deep and settings.llm_enabled:
            ok, detail = brain.client.ping()  # type: ignore[attr-defined]
            out["llm"] = {"reachable": ok, "detail": detail}
        return out

    for router in (auth.router, interviews.router, journey.router, classes.router, harness.router, workspace.router):
        app.include_router(router)

    static = _static_dir(settings)
    if static:
        @app.get("/sw.js", include_in_schema=False)
        def service_worker():
            return FileResponse(static / "sw.js", media_type="application/javascript",
                                headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                from fastapi import HTTPException

                raise HTTPException(404, "Not found")
            candidate = (static / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(static):
                return FileResponse(candidate)
            return FileResponse(static / "index.html")

        log.info("serving frontend from %s", static)
    else:
        log.info("no frontend build found - API-only mode (run `npm run dev` in src/frontend)")
    return app


def __getattr__(name: str):
    # `uvicorn zusage.main:app` keeps working, but importing this module has no
    # side effects (tests build their own app with create_app(settings)).
    if name == "app":
        return create_app()
    raise AttributeError(name)

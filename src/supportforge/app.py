"""FastAPI application factory and same-origin operator console."""

import logging
import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from supportforge import __version__
from supportforge.agent import AgentError, SupportAgent
from supportforge.config import PACKAGE_ROOT, Settings
from supportforge.knowledge import KnowledgeBase
from supportforge.models import ReviewRequest, Run, SupportRequest
from supportforge.store import ConflictError, Store

logger = logging.getLogger("supportforge")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.database)
    knowledge = KnowledgeBase(store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.initialize()
        knowledge.ingest(settings.knowledge_dir)
        app.state.agent = SupportAgent(settings, store, knowledge)
        app.state.store = store
        app.state.knowledge = knowledge
        yield

    app = FastAPI(title="SupportForge API", version=__version__, lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    def authorize(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if settings.api_token and (
            credentials is None
            or not secrets.compare_digest(credentials.credentials, settings.api_token)
        ):
            raise HTTPException(
                status_code=401,
                detail="Valid API token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @app.middleware("http")
    async def headers(request: Request, call_next):
        request_id = secrets.token_hex(8)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        if request.url.path in {"/docs", "/redoc"}:
            # FastAPI's documentation UIs load their assets from the official configured CDN.
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
            )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz", include_in_schema=False)
    def health():
        with store.connect() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "version": __version__}

    router = APIRouter(prefix="/api", dependencies=[Depends(authorize)])

    @router.get("/meta")
    def meta():
        return {
            "name": "SupportForge",
            "version": __version__,
            "mode": settings.mode,
            "model": settings.model if settings.mode == "openai" else None,
            "plugins": ["Knowledge.search", "Triage.classify"],
            "stats": store.stats(),
        }

    @router.get("/knowledge")
    def documents():
        return knowledge.documents()

    @router.post("/runs", response_model=Run, status_code=201)
    async def create_run(
        request: SupportRequest,
        idempotency_key: Annotated[str | None, Header(min_length=1, max_length=100)] = None,
    ):
        try:
            return await app.state.agent.draft(request, idempotency_key)
        except ConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except AgentError as error:
            logger.warning("Draft generation failed; provider details suppressed")
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.get("/runs", response_model=list[Run])
    def list_runs(limit: Annotated[int, Query(ge=1, le=100)] = 50):
        return store.list_runs(limit)

    @router.get("/runs/{run_id}", response_model=Run)
    def get_run(run_id: str):
        result = store.get_run(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result

    @router.post("/runs/{run_id}/review", response_model=Run)
    def review_run(run_id: str, review: ReviewRequest):
        try:
            return store.review(run_id, review)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error
        except ConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/runs/{run_id}/audit")
    def audit(run_id: str):
        get_run(run_id)
        return store.audit(run_id)

    app.include_router(router)
    app.mount("/assets", StaticFiles(directory=PACKAGE_ROOT / "static"), name="assets")

    @app.get("/", include_in_schema=False)
    def console():
        return FileResponse(PACKAGE_ROOT / "static" / "index.html")

    return app

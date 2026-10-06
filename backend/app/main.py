"""FastAPI entrypoint: API under /api, the static frontend served from /."""
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (registers tables)
from app.config import get_settings
from app.database import SessionLocal, engine
from app.errors import register_error_handlers
from app.migrate import upgrade_schema
from app.models import Base
from app.routers import (
    auth, body_metrics, exercises, nutrition, profile, reference, workout_sessions, workouts,
)
from app.seed import seed_reference_data

logging.basicConfig(level=logging.INFO)

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    upgrade_schema(engine)
    if get_settings().seed_on_startup:
        with SessionLocal() as db:
            seed_reference_data(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Liv API", version="0.2.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    register_error_handlers(app)

    @app.middleware("http")
    async def security(request: Request, call_next):
        # CSRF defence in depth (SameSite=Lax cookies are the first layer): a state-changing
        # request carrying a foreign Origin header is rejected.
        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host") \
                    and origin.rstrip("/") not in settings.allowed_origin_list:
                return JSONResponse(
                    {"error": {"code": "forbidden_origin", "message": "Request origin not allowed.",
                               "details": None}}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    for module in (auth, profile, reference, exercises, workouts, workout_sessions,
                   body_metrics, nutrition):
        app.include_router(module.router, prefix="/api")

    if settings.frontend_dir.exists():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()

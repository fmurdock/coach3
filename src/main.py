"""FastAPI Application Factory for Coach3."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import urllib.parse
import uuid
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.router import api_router
from src.core.auth import is_request_authenticated
from src.core.config import settings
from src.core.database import async_session_factory, dispose_engine, get_db
from src.core.http_client import close_shared_http_client
from src.core.logging import configure_logging, request_id_ctx
from src.core.scheduler import (
    recover_orphaned_sync_logs,
    start_scheduler,
    stop_scheduler,
)
from src.services.exercise_catalog import catalog_service

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)

# Paths exempt from session cookie requirement
PUBLIC_PATHS = {
    "/health",
    "/login",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/status",
    "/api/v1/integrations/polar/callback",
    "/api/v1/integrations/concept2/callback",
}

STRICT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Startup: recover orphaned in-progress sync logs & hydrate exercise catalog from DB
    if settings.ENVIRONMENT.lower().strip() != "test":
        try:
            async with async_session_factory() as session:
                recovered = await recover_orphaned_sync_logs(session)
                if recovered:
                    logger.warning("Recovered %d orphaned in-progress sync audit logs on startup", recovered)
                await catalog_service.load_from_db(session)
                await session.commit()
        except Exception as exc:
            logger.warning("Startup DB housekeeping skipped: %s", exc)
        start_scheduler()
    yield
    # Shutdown: gracefully drain scheduler, close HTTP pool, and dispose DB engine
    await stop_scheduler()
    await close_shared_http_client()
    await dispose_engine()


app = FastAPI(
    title="Coach3 Ingestion & Workouts API",
    version="2.0.0",
    description="Self-hosted workout tracker and AI fitness coach backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def security_and_auth_middleware(request: Request, call_next):
    """Inject correlation ID, enforce single-user auth, and attach defense-in-depth security headers."""
    raw_req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    safe_req_id = raw_req_id[:64]
    token = request_id_ctx.set(safe_req_id)

    try:
        path = request.url.path
        is_public = (
            path in PUBLIC_PATHS
            or path.startswith("/static/")
            or request.method == "OPTIONS"
        )

        response: Response
        if not is_public and not is_request_authenticated(request):
            if path.startswith("/api/"):
                response = JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"},
                )
            else:
                next_target = path + (f"?{request.url.query}" if request.url.query else "")
                encoded_next = urllib.parse.quote(next_target, safe="/")
                response = RedirectResponse(url=f"/login?next={encoded_next}", status_code=307)
        else:
            response = await call_next(request)

        # Defense-in-depth browser security headers
        response.headers["X-Request-ID"] = safe_req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(self)"
        if not path.startswith(("/docs", "/redoc")):
            response.headers["Content-Security-Policy"] = STRICT_CSP

        return response
    finally:
        request_id_ctx.reset(token)


app.include_router(api_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}


@app.get("/login", tags=["Authentication"], response_class=FileResponse)
async def login_ui():
    """Serves the single-user passphrase sign-in interface."""
    return FileResponse(STATIC_DIR / "login.html", headers=NO_CACHE_HEADERS)


@app.get("/dashboard", tags=["Dashboard"], response_class=FileResponse)
async def dashboard_ui():
    """Serves the interactive training volume and peak performance dashboard."""
    return FileResponse(STATIC_DIR / "dashboard.html", headers=NO_CACHE_HEADERS)


@app.get("/gym", tags=["Gym Mode"], response_class=FileResponse)
async def gym_ui():
    """Serves the mobile-optimized Gym Mode voice logger interface."""
    return FileResponse(STATIC_DIR / "gym.html", headers=NO_CACHE_HEADERS)


@app.get("/coach", tags=["AI Coach"], response_class=FileResponse)
async def coach_ui():
    """Serves the interactive adaptive AI coaching interface."""
    return FileResponse(STATIC_DIR / "coach.html", headers=NO_CACHE_HEADERS)


@app.get("/config", tags=["Configuration"], response_class=FileResponse)
async def config_ui():
    """Serves the dedicated configuration and integrations setup interface."""
    return FileResponse(STATIC_DIR / "config.html", headers=NO_CACHE_HEADERS)


@app.get("/", tags=["Root"], response_class=FileResponse)
async def root_ui():
    """Default landing interface."""
    return FileResponse(STATIC_DIR / "gym.html", headers=NO_CACHE_HEADERS)


@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Dependency-aware health probe checking live database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "coach3",
            "environment": settings.ENVIRONMENT,
            "database": "connected",
        }
    except Exception as exc:
        logger.error("Health check database probe failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "coach3",
                "environment": settings.ENVIRONMENT,
                "database": "unreachable",
            },
        )

"""FastAPI Application Factory for Coach3."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.router import api_router
from src.core.config import settings
from src.core.scheduler import start_scheduler, stop_scheduler

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start background sync scheduler
    start_scheduler()
    yield
    # Shutdown: gracefully stop scheduler
    stop_scheduler()


app = FastAPI(
    title="Coach3 Ingestion & Workouts API",
    version="1.0.0",
    description="Self-hosted workout tracker and AI fitness coach backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/dashboard", tags=["Dashboard"], response_class=FileResponse)
async def dashboard_ui():
    """Serves the interactive training volume and peak performance dashboard."""
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/gym", tags=["Gym Mode"], response_class=FileResponse)
async def gym_ui():
    """Serves the mobile-optimized Gym Mode voice logger interface."""
    return FileResponse(STATIC_DIR / "gym.html")


@app.get("/", tags=["Root"], response_class=FileResponse)
async def root_ui():
    """Default landing interface."""
    return FileResponse(STATIC_DIR / "gym.html")


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "coach3",
        "environment": settings.ENVIRONMENT,
    }

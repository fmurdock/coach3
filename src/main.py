"""FastAPI Application Factory for Coach3."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.core.config import settings
from src.core.scheduler import start_scheduler, stop_scheduler


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


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "coach3",
        "environment": settings.ENVIRONMENT,
    }

"""Combined API v1 router."""

from fastapi import APIRouter
from src.api.admin import router as admin_router
from src.api.analytics import router as analytics_router
from src.api.auth import router as auth_router
from src.api.coaching import router as coaching_router
from src.api.config import router as config_router
from src.api.diagnostics import router as diagnostics_router
from src.api.export import router as export_router
from src.api.gym import router as gym_router
from src.api.integrations import router as integrations_router
from src.api.profile import router as profile_router
from src.api.workouts import router as workouts_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(config_router)
api_router.include_router(diagnostics_router)
api_router.include_router(export_router)
api_router.include_router(integrations_router)
api_router.include_router(workouts_router)
api_router.include_router(profile_router)
api_router.include_router(gym_router)
api_router.include_router(analytics_router)
api_router.include_router(coaching_router)

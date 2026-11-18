"""Combined API v1 router."""

from fastapi import APIRouter
from src.api.gym import router as gym_router
from src.api.integrations import router as integrations_router
from src.api.profile import router as profile_router
from src.api.workouts import router as workouts_router

api_router = APIRouter()
api_router.include_router(integrations_router)
api_router.include_router(workouts_router)
api_router.include_router(profile_router)
api_router.include_router(gym_router)

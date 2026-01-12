"""API routers for the application."""

from .auth import router as auth_router
from .users import router as users_router
from .subscriptions import router as subscriptions_router
from .credits import router as credits_router
from .schedules import router as schedules_router
from .podcasts import router as podcasts_router
from .payments import router as payments_router

__all__ = [
    "auth_router",
    "users_router",
    "subscriptions_router",
    "credits_router",
    "schedules_router",
    "podcasts_router",
    "payments_router",
]

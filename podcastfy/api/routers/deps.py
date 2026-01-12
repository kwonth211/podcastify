"""FastAPI dependencies for authentication and database access."""

import os
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from supabase import Client

from ..db import get_supabase_client, get_supabase_admin_client
from ..models.user import User
from ..services.auth_service import AuthService
from ..services.user_service import UserService
from ..services.subscription_service import SubscriptionService
from ..services.credits_service import CreditsService
from ..services.schedule_service import ScheduleService
from ..services.podcast_service import PodcastService
from ..services.payment_service import PaymentService


# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# Database dependencies
def get_db() -> Client:
    """Get Supabase client."""
    return get_supabase_client()


def get_admin_db() -> Client:
    """Get Supabase admin client."""
    return get_supabase_admin_client()


# Service dependencies
def get_auth_service(db: Client = Depends(get_db)) -> AuthService:
    """Get authentication service."""
    return AuthService(db)


def get_user_service(db: Client = Depends(get_admin_db)) -> UserService:
    """Get user service."""
    return UserService(db)


def get_subscription_service(db: Client = Depends(get_admin_db)) -> SubscriptionService:
    """Get subscription service."""
    return SubscriptionService(db)


def get_credits_service(db: Client = Depends(get_admin_db)) -> CreditsService:
    """Get credits service."""
    return CreditsService(db)


def get_schedule_service(db: Client = Depends(get_admin_db)) -> ScheduleService:
    """Get schedule service."""
    return ScheduleService(db)


def get_podcast_service(db: Client = Depends(get_admin_db)) -> PodcastService:
    """Get podcast service."""
    return PodcastService(db)


def get_payment_service(db: Client = Depends(get_admin_db)) -> PaymentService:
    """Get payment service."""
    return PaymentService(db)


# Authentication dependencies
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[User]:
    """
    Get current user from JWT token (optional).
    Returns None if no valid token provided.
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    user = await auth_service.get_current_user(token)
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    Get current user from JWT token (required).
    Raises 401 if no valid token.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    user = await auth_service.get_current_user(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> bool:
    """
    Verify API key for service-to-service calls.
    """
    expected_key = os.getenv("API_KEY", "")
    
    if not expected_key:
        # API key not configured, allow all requests
        return True
    
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or missing API key"},
            headers={"WWW-Authenticate": "API-Key"},
        )
    
    return True


async def get_current_user_or_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[User]:
    """
    Get current user from JWT or validate API key.
    Used for endpoints that support both auth methods.
    """
    # Try JWT first
    if credentials:
        token = credentials.credentials
        user = await auth_service.get_current_user(token)
        if user:
            return user
    
    # Try API key
    expected_key = os.getenv("API_KEY", "")
    if expected_key and api_key == expected_key:
        return None  # API key valid but no user context
    
    # Neither valid
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Authentication required"},
    )

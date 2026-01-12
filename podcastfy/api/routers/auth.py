"""Authentication router for Google OAuth and JWT management."""

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.auth import (
    GoogleAuthRequest,
    AuthResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    AuthUserInfo,
)
from ..models.common import APIResponse, SuccessResponse
from ..models.user import User
from ..services.auth_service import AuthService
from ..services.user_service import UserService
from ..services.subscription_service import SubscriptionService
from .deps import (
    get_auth_service,
    get_user_service,
    get_subscription_service,
    get_current_user,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google", response_model=APIResponse[AuthResponse])
async def google_auth(
    request: GoogleAuthRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Authenticate with Google OAuth.
    
    Exchange Google authorization code for access and refresh tokens.
    Creates a new user if they don't exist.
    
    **Note**: For production, use Supabase Auth directly with their OAuth flow.
    Configure Google OAuth in your Supabase project settings.
    """
    try:
        # This endpoint is mainly for reference
        # In production, use Supabase Auth's built-in OAuth flow
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "code": "NOT_IMPLEMENTED",
                "message": "Use Supabase Auth UI or redirect flow for Google OAuth. "
                           "See: https://supabase.com/docs/guides/auth/social-login/auth-google"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )


@router.get("/me", response_model=APIResponse[AuthUserInfo])
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get current authenticated user information.
    
    Requires Bearer token in Authorization header.
    """
    return APIResponse(
        success=True,
        data=AuthUserInfo(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            picture=current_user.picture,
        )
    )


@router.post("/refresh", response_model=APIResponse[RefreshTokenResponse])
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Refresh access token using refresh token.
    
    Returns a new access token if the refresh token is valid.
    """
    new_access_token = await auth_service.refresh_access_token(request.refresh_token)
    
    if not new_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or expired refresh token"}
        )
    
    return APIResponse(
        success=True,
        data=RefreshTokenResponse(
            access_token=new_access_token,
        )
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(get_current_user),
):
    """
    Logout current user.
    
    Invalidates the current session. Client should discard tokens.
    """
    # In a JWT-based system, logout is typically client-side
    # For enhanced security, implement token blacklisting with Redis
    return SuccessResponse(success=True, message="Logged out successfully")


@router.post("/verify", response_model=APIResponse[AuthUserInfo])
async def verify_token(
    current_user: User = Depends(get_current_user),
):
    """
    Verify if the current token is valid.
    
    Returns user info if token is valid, 401 otherwise.
    """
    return APIResponse(
        success=True,
        data=AuthUserInfo(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            picture=current_user.picture,
        )
    )

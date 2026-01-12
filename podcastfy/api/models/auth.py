"""Authentication models."""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from uuid import UUID


class GoogleAuthRequest(BaseModel):
    """Request for Google OAuth authentication."""
    code: str = Field(..., description="Google authorization code")
    redirect_uri: str = Field(..., description="OAuth redirect URI")


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str = Field(..., description="Subject (user ID)")
    email: str
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")
    type: str = Field(default="access", description="Token type")


class AuthTokens(BaseModel):
    """Authentication tokens."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = Field(default=3600, description="Expiration in seconds")


class AuthResponse(BaseModel):
    """Response for authentication."""
    token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 3600
    user: "AuthUserInfo"


class AuthUserInfo(BaseModel):
    """User info included in auth response."""
    id: UUID
    email: str
    name: str
    picture: Optional[str] = None

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response for token refresh."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600


class LogoutRequest(BaseModel):
    """Request for logout."""
    refresh_token: Optional[str] = None


class PasswordResetRequest(BaseModel):
    """Request for password reset (if using email/password auth)."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset."""
    token: str
    new_password: str = Field(..., min_length=8)


# Update forward reference
AuthResponse.model_rebuild()

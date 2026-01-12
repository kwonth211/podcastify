"""User models."""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    """Base user model with common fields."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    picture: Optional[str] = None


class UserCreate(UserBase):
    """Model for creating a new user."""
    google_id: Optional[str] = None
    supabase_auth_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    """Model for updating user data."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    picture: Optional[str] = None


class User(UserBase):
    """Full user model with all fields."""
    id: UUID
    google_id: Optional[str] = None
    auth_provider: str = "google"
    supabase_auth_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """User response for API endpoints."""
    id: UUID
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserWithStats(UserResponse):
    """User response with additional statistics."""
    plan_id: str = "free"
    subscription_status: str = "active"
    generations_used: int = 0
    generations_limit: int = 1
    batch_tokens_remaining: int = 0
    active_schedules: int = 0
    total_podcasts: int = 0

    class Config:
        from_attributes = True

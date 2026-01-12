"""Schedule models."""

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator
from datetime import datetime, time
from uuid import UUID
from enum import Enum


class DayOfWeek(str, Enum):
    """Day of week enumeration."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ScheduleBase(BaseModel):
    """Base schedule model."""
    name: str = Field(default="My Schedule", max_length=255)
    prompt: str = Field(..., min_length=1, description="Search prompt for news")
    days: List[DayOfWeek] = Field(..., min_length=1, description="Days to run")
    time: str = Field(..., description="Time to run (HH:MM format)")
    timezone: str = Field(default="Asia/Seoul", description="IANA timezone")
    email: EmailStr = Field(..., description="Email for delivery")
    language: str = Field(default="ko", description="Output language code")
    tts_model: str = Field(default="gemini", description="TTS model to use")
    is_active: bool = True

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time is in HH:MM format."""
        try:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError()
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, IndexError):
            raise ValueError("Time must be in HH:MM format (00:00 - 23:59)")


class ScheduleCreate(ScheduleBase):
    """Model for creating a schedule."""
    user_id: Optional[UUID] = None  # Set from auth context


class ScheduleUpdate(BaseModel):
    """Model for updating a schedule."""
    name: Optional[str] = Field(None, max_length=255)
    prompt: Optional[str] = Field(None, min_length=1)
    days: Optional[List[DayOfWeek]] = Field(None, min_length=1)
    time: Optional[str] = None
    timezone: Optional[str] = None
    email: Optional[EmailStr] = None
    language: Optional[str] = None
    tts_model: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time is in HH:MM format."""
        if v is None:
            return None
        try:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError()
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, IndexError):
            raise ValueError("Time must be in HH:MM format (00:00 - 23:59)")


class Schedule(ScheduleBase):
    """Full schedule model."""
    id: UUID
    user_id: UUID
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    failure_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScheduleResponse(BaseModel):
    """Schedule response for API."""
    id: UUID
    user_id: UUID
    name: str
    prompt: str
    days: List[str]
    time: str
    timezone: str
    email: str
    language: str
    tts_model: str
    is_active: bool
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScheduleTestResponse(BaseModel):
    """Response for schedule test execution."""
    podcast_id: UUID
    status: str = "generating"


class ScheduleListResponse(BaseModel):
    """Response for schedule list."""
    schedules: List[ScheduleResponse]
    total: int

"""Podcast models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from enum import Enum


class PodcastStatus(str, Enum):
    """Podcast generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationStep(str, Enum):
    """Podcast generation steps."""
    PROMPTING = "prompting"
    CRAWLING = "crawling"
    SUMMARIZING = "summarizing"
    GENERATING = "generating"
    COMPLETED = "completed"


class StepStatus(BaseModel):
    """Status of a generation step."""
    id: str
    status: str  # pending, in_progress, completed, failed
    message: Optional[str] = None


class PodcastBase(BaseModel):
    """Base podcast model."""
    prompt: str = Field(..., min_length=1, description="Generation prompt")


class PodcastCreate(PodcastBase):
    """Model for creating a podcast."""
    user_id: Optional[UUID] = None
    schedule_id: Optional[UUID] = None


class PodcastGenerateRequest(BaseModel):
    """Request for generating a podcast."""
    prompt: str = Field(
        ..., 
        min_length=1,
        description="Search prompt (e.g., 'AI 뉴스', '정치 뉴스')"
    )
    language: str = Field(default="ko", description="Output language")
    tts_model: str = Field(default="gemini", description="TTS model")
    longform: bool = Field(default=False, description="Generate long-form podcast")


class Podcast(PodcastBase):
    """Full podcast model."""
    id: UUID
    user_id: UUID
    schedule_id: Optional[UUID] = None
    title: Optional[str] = None
    script: Optional[str] = None
    audio_url: Optional[str] = None
    transcript_url: Optional[str] = None
    sources_url: Optional[str] = None
    duration: Optional[int] = None  # seconds
    file_size: Optional[int] = None  # bytes
    status: PodcastStatus = PodcastStatus.PENDING
    progress: int = 0
    current_step: Optional[str] = None
    play_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PodcastResponse(BaseModel):
    """Podcast response for API."""
    id: UUID
    user_id: UUID
    schedule_id: Optional[UUID] = None
    prompt: str
    title: Optional[str] = None
    audio_url: Optional[str] = None
    transcript_url: Optional[str] = None
    duration: Optional[int] = None
    status: PodcastStatus
    play_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class PodcastDetailResponse(PodcastResponse):
    """Detailed podcast response."""
    script: Optional[str] = None
    sources_url: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class PodcastStatusResponse(BaseModel):
    """Response for podcast generation status."""
    id: UUID
    status: PodcastStatus
    progress: int = Field(..., ge=0, le=100)
    current_step: Optional[str] = None
    steps: List[StepStatus] = Field(default_factory=list)
    error_message: Optional[str] = None

    @classmethod
    def from_podcast(cls, podcast: Podcast) -> "PodcastStatusResponse":
        """Create status response from podcast."""
        steps = [
            StepStatus(id="prompting", status="pending"),
            StepStatus(id="crawling", status="pending"),
            StepStatus(id="summarizing", status="pending"),
            StepStatus(id="generating", status="pending"),
        ]
        
        # Update step statuses based on progress
        step_progress = {
            "prompting": 10,
            "crawling": 40,
            "summarizing": 70,
            "generating": 90,
        }
        
        for step in steps:
            threshold = step_progress.get(step.id, 0)
            if podcast.progress >= threshold:
                if step.id == podcast.current_step:
                    step.status = "in_progress"
                elif podcast.progress > threshold:
                    step.status = "completed"
        
        if podcast.status == PodcastStatus.COMPLETED:
            for step in steps:
                step.status = "completed"
        elif podcast.status == PodcastStatus.FAILED:
            for step in steps:
                if step.id == podcast.current_step:
                    step.status = "failed"
                    step.message = podcast.error_message
        
        return cls(
            id=podcast.id,
            status=podcast.status,
            progress=podcast.progress,
            current_step=podcast.current_step,
            steps=steps,
            error_message=podcast.error_message,
        )


class PodcastGenerateResponse(BaseModel):
    """Response for podcast generation request."""
    podcast_id: UUID
    status: PodcastStatus = PodcastStatus.GENERATING
    estimated_time: int = Field(default=120, description="Estimated time in seconds")


class PodcastListResponse(BaseModel):
    """Response for podcast list."""
    podcasts: List[PodcastResponse]
    total: int
    limit: int
    offset: int

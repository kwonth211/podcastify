"""Podcast service for podcast generation and management."""

from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from supabase import Client

from ..models.podcast import (
    Podcast,
    PodcastCreate,
    PodcastResponse,
    PodcastDetailResponse,
    PodcastStatus,
    PodcastStatusResponse,
    PodcastGenerateResponse,
    PodcastListResponse,
)
from ..utils.exceptions import NotFoundError, InsufficientCreditsError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PodcastService:
    """Service for podcast operations."""
    
    def __init__(self, db: Client):
        self.db = db
    
    async def get_podcast_by_id(self, podcast_id: UUID) -> Optional[Podcast]:
        """Get podcast by ID."""
        result = self.db.table("podcasts").select("*").eq(
            "id", str(podcast_id)
        ).execute()
        
        if not result.data:
            return None
        
        return Podcast(**result.data[0])
    
    async def get_podcasts_by_user_id(
        self,
        user_id: UUID,
        status: Optional[PodcastStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PodcastListResponse:
        """Get paginated podcasts for a user."""
        query = self.db.table("podcasts").select("*", count="exact").eq(
            "user_id", str(user_id)
        )
        
        if status:
            query = query.eq("status", status.value)
        
        result = query.order("created_at", desc=True).range(
            offset, offset + limit - 1
        ).execute()
        
        podcasts = [PodcastResponse(**row) for row in result.data]
        total = result.count or 0
        
        return PodcastListResponse(
            podcasts=podcasts,
            total=total,
            limit=limit,
            offset=offset,
        )
    
    async def create_podcast(
        self,
        user_id: UUID,
        prompt: str,
        schedule_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Podcast:
        """Create a new podcast record."""
        insert_data = {
            "user_id": str(user_id),
            "prompt": prompt,
            "status": PodcastStatus.PENDING.value,
            "progress": 0,
            "metadata": metadata or {},
        }
        
        if schedule_id:
            insert_data["schedule_id"] = str(schedule_id)
        
        result = self.db.table("podcasts").insert(insert_data).execute()
        
        if not result.data:
            raise Exception("Failed to create podcast")
        
        logger.info(f"Created podcast {result.data[0]['id']} for user {user_id}")
        return Podcast(**result.data[0])
    
    async def update_podcast_status(
        self,
        podcast_id: UUID,
        status: PodcastStatus,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Podcast:
        """Update podcast generation status."""
        update_data = {"status": status.value}
        
        if progress is not None:
            update_data["progress"] = progress
        
        if current_step is not None:
            update_data["current_step"] = current_step
        
        if error_message is not None:
            update_data["error_message"] = error_message
        
        result = self.db.table("podcasts").update(update_data).eq(
            "id", str(podcast_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Podcast", str(podcast_id))
        
        logger.info(f"Updated podcast {podcast_id} status to {status.value}")
        return Podcast(**result.data[0])
    
    async def complete_podcast(
        self,
        podcast_id: UUID,
        title: str,
        audio_url: str,
        transcript_url: Optional[str] = None,
        sources_url: Optional[str] = None,
        script: Optional[str] = None,
        duration: Optional[int] = None,
        file_size: Optional[int] = None,
    ) -> Podcast:
        """Mark podcast as completed with all metadata."""
        update_data = {
            "status": PodcastStatus.COMPLETED.value,
            "progress": 100,
            "current_step": "completed",
            "title": title,
            "audio_url": audio_url,
        }
        
        if transcript_url:
            update_data["transcript_url"] = transcript_url
        if sources_url:
            update_data["sources_url"] = sources_url
        if script:
            update_data["script"] = script
        if duration:
            update_data["duration"] = duration
        if file_size:
            update_data["file_size"] = file_size
        
        result = self.db.table("podcasts").update(update_data).eq(
            "id", str(podcast_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Podcast", str(podcast_id))
        
        logger.info(f"Completed podcast {podcast_id}: {title}")
        return Podcast(**result.data[0])
    
    async def fail_podcast(
        self,
        podcast_id: UUID,
        error_message: str,
        current_step: Optional[str] = None,
    ) -> Podcast:
        """Mark podcast as failed."""
        update_data = {
            "status": PodcastStatus.FAILED.value,
            "error_message": error_message,
        }
        
        if current_step:
            update_data["current_step"] = current_step
        
        result = self.db.table("podcasts").update(update_data).eq(
            "id", str(podcast_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Podcast", str(podcast_id))
        
        logger.error(f"Failed podcast {podcast_id}: {error_message}")
        return Podcast(**result.data[0])
    
    async def increment_play_count(self, podcast_id: UUID) -> Podcast:
        """Increment podcast play count."""
        existing = await self.get_podcast_by_id(podcast_id)
        if not existing:
            raise NotFoundError("Podcast", str(podcast_id))
        
        result = self.db.table("podcasts").update({
            "play_count": existing.play_count + 1,
        }).eq("id", str(podcast_id)).execute()
        
        if not result.data:
            raise NotFoundError("Podcast", str(podcast_id))
        
        return Podcast(**result.data[0])
    
    async def delete_podcast(
        self,
        podcast_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """Delete a podcast."""
        existing = await self.get_podcast_by_id(podcast_id)
        if not existing:
            raise NotFoundError("Podcast", str(podcast_id))
        
        if user_id and existing.user_id != user_id:
            raise NotFoundError("Podcast", str(podcast_id))
        
        self.db.table("podcasts").delete().eq(
            "id", str(podcast_id)
        ).execute()
        
        logger.info(f"Deleted podcast {podcast_id}")
        return True
    
    async def get_podcast_status(self, podcast_id: UUID) -> PodcastStatusResponse:
        """Get detailed status for a podcast."""
        podcast = await self.get_podcast_by_id(podcast_id)
        if not podcast:
            raise NotFoundError("Podcast", str(podcast_id))
        
        return PodcastStatusResponse.from_podcast(podcast)
    
    async def get_recent_podcasts(
        self,
        user_id: UUID,
        limit: int = 5,
    ) -> List[PodcastResponse]:
        """Get recent completed podcasts for a user."""
        result = self.db.table("podcasts").select("*").eq(
            "user_id", str(user_id)
        ).eq("status", PodcastStatus.COMPLETED.value).order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        return [PodcastResponse(**row) for row in result.data]
    
    async def get_user_podcast_count(
        self,
        user_id: UUID,
        since: Optional[datetime] = None,
    ) -> int:
        """Get count of podcasts for a user."""
        query = self.db.table("podcasts").select("*", count="exact").eq(
            "user_id", str(user_id)
        )
        
        if since:
            query = query.gte("created_at", since.isoformat())
        
        result = query.execute()
        return result.count or 0

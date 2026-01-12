"""Podcasts router for podcast management and generation."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse
import os

from ..models.podcast import (
    Podcast,
    PodcastResponse,
    PodcastDetailResponse,
    PodcastStatus,
    PodcastStatusResponse,
    PodcastGenerateRequest,
    PodcastGenerateResponse,
    PodcastListResponse,
)
from ..models.common import APIResponse, SuccessResponse
from ..models.user import User
from ..services.podcast_service import PodcastService
from ..services.credits_service import CreditsService
from ..utils.exceptions import InsufficientCreditsError, NotFoundError
from .deps import (
    get_podcast_service,
    get_credits_service,
    get_current_user,
    verify_api_key,
)


router = APIRouter(prefix="/podcasts", tags=["Podcasts"])

# Base directory for files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
AUDIO_DIR = os.path.join(BASE_DIR, "data", "audio", "tmp")
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "data", "transcripts")
SOURCES_DIR = os.path.join(BASE_DIR, "data", "sources")


@router.get("/me", response_model=APIResponse[PodcastListResponse])
async def get_my_podcasts(
    status_filter: Optional[PodcastStatus] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    podcast_service: PodcastService = Depends(get_podcast_service),
):
    """
    Get all podcasts for the current user.
    """
    result = await podcast_service.get_podcasts_by_user_id(
        user_id=current_user.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    
    return APIResponse(success=True, data=result)


@router.get("/user/{user_id}", response_model=APIResponse[PodcastListResponse])
async def get_user_podcasts(
    user_id: UUID,
    status_filter: Optional[PodcastStatus] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    podcast_service: PodcastService = Depends(get_podcast_service),
):
    """
    Get all podcasts for a specific user.
    
    Users can only view their own podcasts.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot view other users' podcasts"}
        )
    
    result = await podcast_service.get_podcasts_by_user_id(
        user_id=user_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    
    return APIResponse(success=True, data=result)


@router.post("/generate", response_model=APIResponse[PodcastGenerateResponse])
async def generate_podcast(
    request: PodcastGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    podcast_service: PodcastService = Depends(get_podcast_service),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Generate a new podcast from a prompt.
    
    This uses one credit from the user's balance.
    The podcast is generated asynchronously - use the status endpoint to track progress.
    """
    # Check and use credit
    try:
        await credits_service.use_credit(current_user.id)
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message}
        )
    
    # Create podcast record
    podcast = await podcast_service.create_podcast(
        user_id=current_user.id,
        prompt=request.prompt,
        metadata={
            "language": request.language,
            "tts_model": request.tts_model,
            "longform": request.longform,
        }
    )
    
    # Update status to generating
    await podcast_service.update_podcast_status(
        podcast_id=podcast.id,
        status=PodcastStatus.GENERATING,
        progress=0,
        current_step="prompting",
    )
    
    # Add background task to generate podcast
    # Note: In production, use a proper task queue like Celery or Redis Queue
    background_tasks.add_task(
        _generate_podcast_task,
        podcast_id=podcast.id,
        prompt=request.prompt,
        language=request.language,
        tts_model=request.tts_model,
        longform=request.longform,
    )
    
    return APIResponse(
        success=True,
        data=PodcastGenerateResponse(
            podcast_id=podcast.id,
            status=PodcastStatus.GENERATING,
            estimated_time=120,
        )
    )


async def _generate_podcast_task(
    podcast_id: UUID,
    prompt: str,
    language: str,
    tts_model: str,
    longform: bool,
):
    """
    Background task to generate a podcast.
    
    This is a simplified version - in production, use proper task queues.
    """
    from ..db import get_supabase_admin_client
    from ..services.podcast_service import PodcastService
    
    db = get_supabase_admin_client()
    podcast_service = PodcastService(db)
    
    try:
        # Import the existing podcast generation logic
        from ...client import generate_podcast as generate_podcast_audio
        from ...utils.config_conversation import load_conversation_config
        
        # Update progress: prompting
        await podcast_service.update_podcast_status(
            podcast_id=podcast_id,
            status=PodcastStatus.GENERATING,
            progress=10,
            current_step="prompting",
        )
        
        # Configure conversation
        conv_config = load_conversation_config().to_dict()
        lang_map = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}
        conv_config["output_language"] = lang_map.get(language, "English")
        
        # Update progress: crawling
        await podcast_service.update_podcast_status(
            podcast_id=podcast_id,
            status=PodcastStatus.GENERATING,
            progress=40,
            current_step="crawling",
        )
        
        # Update progress: summarizing
        await podcast_service.update_podcast_status(
            podcast_id=podcast_id,
            status=PodcastStatus.GENERATING,
            progress=70,
            current_step="summarizing",
        )
        
        # Generate podcast
        audio_file = generate_podcast_audio(
            topic=prompt,
            tts_model=tts_model,
            conversation_config=conv_config,
            longform=longform,
        )
        
        # Update progress: generating audio
        await podcast_service.update_podcast_status(
            podcast_id=podcast_id,
            status=PodcastStatus.GENERATING,
            progress=90,
            current_step="generating",
        )
        
        if audio_file and os.path.isfile(audio_file):
            # Extract filename
            filename = os.path.basename(audio_file)
            audio_url = f"/api/v2/podcasts/audio/{filename}"
            
            # Get file size
            file_size = os.path.getsize(audio_file)
            
            # Complete the podcast
            await podcast_service.complete_podcast(
                podcast_id=podcast_id,
                title=f"News Podcast - {prompt[:50]}",
                audio_url=audio_url,
                duration=0,  # Could calculate from audio file
                file_size=file_size,
            )
        else:
            await podcast_service.fail_podcast(
                podcast_id=podcast_id,
                error_message="Failed to generate audio file",
                current_step="generating",
            )
            
    except Exception as e:
        await podcast_service.fail_podcast(
            podcast_id=podcast_id,
            error_message=str(e),
        )


@router.get("/{podcast_id}", response_model=APIResponse[PodcastDetailResponse])
async def get_podcast(
    podcast_id: UUID,
    current_user: User = Depends(get_current_user),
    podcast_service: PodcastService = Depends(get_podcast_service),
):
    """
    Get a specific podcast by ID.
    """
    podcast = await podcast_service.get_podcast_by_id(podcast_id)
    
    if not podcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Podcast not found"}
        )
    
    if podcast.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot access this podcast"}
        )
    
    return APIResponse(
        success=True,
        data=PodcastDetailResponse(
            id=podcast.id,
            user_id=podcast.user_id,
            schedule_id=podcast.schedule_id,
            prompt=podcast.prompt,
            title=podcast.title,
            script=podcast.script,
            audio_url=podcast.audio_url,
            transcript_url=podcast.transcript_url,
            sources_url=podcast.sources_url,
            duration=podcast.duration,
            file_size=podcast.file_size,
            status=podcast.status,
            error_message=podcast.error_message,
            play_count=podcast.play_count,
            metadata=podcast.metadata,
            created_at=podcast.created_at,
            updated_at=podcast.updated_at,
        )
    )


@router.get("/{podcast_id}/status", response_model=APIResponse[PodcastStatusResponse])
async def get_podcast_status(
    podcast_id: UUID,
    current_user: User = Depends(get_current_user),
    podcast_service: PodcastService = Depends(get_podcast_service),
):
    """
    Get generation status for a podcast.
    
    Use this endpoint to poll for progress during generation.
    """
    podcast = await podcast_service.get_podcast_by_id(podcast_id)
    
    if not podcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Podcast not found"}
        )
    
    if podcast.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot access this podcast"}
        )
    
    status_response = await podcast_service.get_podcast_status(podcast_id)
    return APIResponse(success=True, data=status_response)


@router.post("/{podcast_id}/play", response_model=SuccessResponse)
async def record_play(
    podcast_id: UUID,
    current_user: User = Depends(get_current_user),
    podcast_service: PodcastService = Depends(get_podcast_service),
):
    """
    Record a play count for a podcast.
    """
    podcast = await podcast_service.get_podcast_by_id(podcast_id)
    
    if not podcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Podcast not found"}
        )
    
    if podcast.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot access this podcast"}
        )
    
    await podcast_service.increment_play_count(podcast_id)
    return SuccessResponse(success=True, message="Play recorded")


@router.delete("/{podcast_id}", response_model=SuccessResponse)
async def delete_podcast(
    podcast_id: UUID,
    current_user: User = Depends(get_current_user),
    podcast_service: PodcastService = Depends(get_podcast_service),
):
    """
    Delete a podcast.
    """
    await podcast_service.delete_podcast(podcast_id, user_id=current_user.id)
    return SuccessResponse(success=True, message="Podcast deleted successfully")


# File serving endpoints
@router.get("/audio/{filename}")
async def serve_audio(
    filename: str,
    _: bool = Depends(verify_api_key),
):
    """
    Serve audio file.
    """
    file_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Audio file not found"}
        )
    return FileResponse(file_path, media_type="audio/mpeg", filename=filename)


@router.get("/transcripts/{filename}")
async def serve_transcript(
    filename: str,
    _: bool = Depends(verify_api_key),
):
    """
    Serve transcript file.
    """
    file_path = os.path.join(TRANSCRIPTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Transcript not found"}
        )
    return FileResponse(
        file_path, 
        media_type="text/plain; charset=utf-8", 
        filename=filename
    )


@router.get("/sources/{filename}")
async def serve_sources(
    filename: str,
    _: bool = Depends(verify_api_key),
):
    """
    Serve news sources JSON file.
    """
    file_path = os.path.join(SOURCES_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Sources file not found"}
        )
    return FileResponse(file_path, media_type="application/json", filename=filename)

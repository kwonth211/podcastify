"""Schedules router for managing podcast schedules."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.schedule import (
    Schedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleListResponse,
    ScheduleTestResponse,
)
from ..models.common import APIResponse, SuccessResponse
from ..models.user import User
from ..services.schedule_service import ScheduleService
from ..services.subscription_service import SubscriptionService
from ..services.credits_service import CreditsService
from ..services.podcast_service import PodcastService
from ..utils.exceptions import ScheduleLimitExceededError, InsufficientBatchTokensError
from .deps import (
    get_schedule_service,
    get_subscription_service,
    get_credits_service,
    get_podcast_service,
    get_current_user,
)


router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.get("/me", response_model=APIResponse[ScheduleListResponse])
async def get_my_schedules(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    """
    Get all schedules for the current user.
    """
    schedules = await schedule_service.get_schedules_by_user_id(
        current_user.id, 
        active_only=active_only
    )
    
    schedule_responses = [
        ScheduleResponse(
            id=s.id,
            user_id=s.user_id,
            name=s.name,
            prompt=s.prompt,
            days=[d for d in s.days],
            time=s.time,
            timezone=s.timezone,
            email=s.email,
            language=s.language,
            tts_model=s.tts_model,
            is_active=s.is_active,
            last_run=s.last_run,
            next_run=s.next_run,
            run_count=s.run_count,
            failure_count=s.failure_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in schedules
    ]
    
    return APIResponse(
        success=True,
        data=ScheduleListResponse(
            schedules=schedule_responses,
            total=len(schedule_responses),
        )
    )


@router.get("/user/{user_id}", response_model=APIResponse[ScheduleListResponse])
async def get_user_schedules(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    """
    Get all schedules for a specific user.
    
    Users can only view their own schedules.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot view other users' schedules"}
        )
    
    schedules = await schedule_service.get_schedules_by_user_id(user_id)
    
    schedule_responses = [
        ScheduleResponse(
            id=s.id,
            user_id=s.user_id,
            name=s.name,
            prompt=s.prompt,
            days=[d for d in s.days],
            time=s.time,
            timezone=s.timezone,
            email=s.email,
            language=s.language,
            tts_model=s.tts_model,
            is_active=s.is_active,
            last_run=s.last_run,
            next_run=s.next_run,
            run_count=s.run_count,
            failure_count=s.failure_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in schedules
    ]
    
    return APIResponse(
        success=True,
        data=ScheduleListResponse(
            schedules=schedule_responses,
            total=len(schedule_responses),
        )
    )


@router.post("", response_model=APIResponse[ScheduleResponse])
async def create_schedule(
    schedule_data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Create a new schedule.
    
    Validates schedule limits based on user's plan.
    """
    # Set user_id from auth context
    schedule_data.user_id = current_user.id
    
    # Get user's plan
    subscription = await subscription_service.get_subscription_by_user_id(current_user.id)
    plan_id = subscription.plan_id if subscription else "free"
    
    # Check batch token availability
    has_tokens = await credits_service.check_batch_token_availability(current_user.id)
    if not has_tokens:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "INSUFFICIENT_BATCH_TOKENS",
                "message": "No batch tokens available. Schedules require batch tokens to run."
            }
        )
    
    try:
        schedule = await schedule_service.create_schedule(schedule_data, plan_id)
        
        return APIResponse(
            success=True,
            data=ScheduleResponse(
                id=schedule.id,
                user_id=schedule.user_id,
                name=schedule.name,
                prompt=schedule.prompt,
                days=[d for d in schedule.days],
                time=schedule.time,
                timezone=schedule.timezone,
                email=schedule.email,
                language=schedule.language,
                tts_model=schedule.tts_model,
                is_active=schedule.is_active,
                last_run=schedule.last_run,
                next_run=schedule.next_run,
                run_count=schedule.run_count,
                failure_count=schedule.failure_count,
                created_at=schedule.created_at,
                updated_at=schedule.updated_at,
            )
        )
    except ScheduleLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message}
        )


@router.get("/{schedule_id}", response_model=APIResponse[ScheduleResponse])
async def get_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    """
    Get a specific schedule by ID.
    """
    schedule = await schedule_service.get_schedule_by_id(schedule_id)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Schedule not found"}
        )
    
    if schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot access this schedule"}
        )
    
    return APIResponse(
        success=True,
        data=ScheduleResponse(
            id=schedule.id,
            user_id=schedule.user_id,
            name=schedule.name,
            prompt=schedule.prompt,
            days=[d for d in schedule.days],
            time=schedule.time,
            timezone=schedule.timezone,
            email=schedule.email,
            language=schedule.language,
            tts_model=schedule.tts_model,
            is_active=schedule.is_active,
            last_run=schedule.last_run,
            next_run=schedule.next_run,
            run_count=schedule.run_count,
            failure_count=schedule.failure_count,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )
    )


@router.patch("/{schedule_id}", response_model=APIResponse[ScheduleResponse])
async def update_schedule(
    schedule_id: UUID,
    schedule_data: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    """
    Update a schedule.
    """
    schedule = await schedule_service.update_schedule(
        schedule_id, 
        schedule_data,
        user_id=current_user.id,
    )
    
    return APIResponse(
        success=True,
        data=ScheduleResponse(
            id=schedule.id,
            user_id=schedule.user_id,
            name=schedule.name,
            prompt=schedule.prompt,
            days=[d for d in schedule.days],
            time=schedule.time,
            timezone=schedule.timezone,
            email=schedule.email,
            language=schedule.language,
            tts_model=schedule.tts_model,
            is_active=schedule.is_active,
            last_run=schedule.last_run,
            next_run=schedule.next_run,
            run_count=schedule.run_count,
            failure_count=schedule.failure_count,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )
    )


@router.delete("/{schedule_id}", response_model=SuccessResponse)
async def delete_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    """
    Delete a schedule.
    """
    await schedule_service.delete_schedule(schedule_id, user_id=current_user.id)
    return SuccessResponse(success=True, message="Schedule deleted successfully")


@router.post("/{schedule_id}/toggle", response_model=APIResponse[ScheduleResponse])
async def toggle_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    """
    Toggle schedule active status.
    """
    schedule = await schedule_service.toggle_schedule(
        schedule_id, 
        user_id=current_user.id
    )
    
    return APIResponse(
        success=True,
        data=ScheduleResponse(
            id=schedule.id,
            user_id=schedule.user_id,
            name=schedule.name,
            prompt=schedule.prompt,
            days=[d for d in schedule.days],
            time=schedule.time,
            timezone=schedule.timezone,
            email=schedule.email,
            language=schedule.language,
            tts_model=schedule.tts_model,
            is_active=schedule.is_active,
            last_run=schedule.last_run,
            next_run=schedule.next_run,
            run_count=schedule.run_count,
            failure_count=schedule.failure_count,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )
    )


@router.post("/{schedule_id}/test", response_model=APIResponse[ScheduleTestResponse])
async def test_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    schedule_service: ScheduleService = Depends(get_schedule_service),
    credits_service: CreditsService = Depends(get_credits_service),
    podcast_service: PodcastService = Depends(get_podcast_service),
):
    """
    Test run a schedule immediately.
    
    This uses a batch token (not regular credits).
    """
    schedule = await schedule_service.get_schedule_by_id(schedule_id)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Schedule not found"}
        )
    
    if schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot test this schedule"}
        )
    
    # Check and use batch token
    try:
        await credits_service.use_batch_token(current_user.id)
    except InsufficientBatchTokensError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message}
        )
    
    # Create podcast record
    podcast = await podcast_service.create_podcast(
        user_id=current_user.id,
        prompt=schedule.prompt,
        schedule_id=schedule.id,
        metadata={
            "language": schedule.language,
            "tts_model": schedule.tts_model,
            "test_run": True,
        }
    )
    
    # Note: The actual generation would be triggered by a background task/worker
    # Here we just return the podcast ID for status tracking
    
    return APIResponse(
        success=True,
        data=ScheduleTestResponse(
            podcast_id=podcast.id,
            status="generating",
        )
    )

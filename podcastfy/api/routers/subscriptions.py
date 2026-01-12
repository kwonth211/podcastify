"""Subscriptions router for subscription management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.subscription import (
    SubscriptionResponse,
    PlanType,
    PlanFeatures,
    PLAN_CONFIGS,
    CancelSubscriptionResponse,
)
from ..models.common import APIResponse
from ..models.user import User
from ..services.subscription_service import SubscriptionService
from .deps import get_subscription_service, get_current_user


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/plans", response_model=APIResponse[dict])
async def get_available_plans():
    """
    Get all available subscription plans with their features.
    
    No authentication required.
    """
    plans = {
        plan_id.value: plan_config.model_dump()
        for plan_id, plan_config in PLAN_CONFIGS.items()
    }
    
    return APIResponse(success=True, data={"plans": plans})


@router.get("/me", response_model=APIResponse[SubscriptionResponse])
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Get current user's subscription.
    """
    subscription = await subscription_service.get_subscription_response(current_user.id)
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Subscription not found"}
        )
    
    return APIResponse(success=True, data=subscription)


@router.get("/user/{user_id}", response_model=APIResponse[SubscriptionResponse])
async def get_user_subscription(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Get subscription for a specific user.
    
    Users can only view their own subscription.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot view other users' subscriptions"}
        )
    
    subscription = await subscription_service.get_subscription_response(user_id)
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Subscription not found"}
        )
    
    return APIResponse(success=True, data=subscription)


@router.post("/me/cancel", response_model=APIResponse[CancelSubscriptionResponse])
async def cancel_current_subscription(
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Cancel current subscription.
    
    The subscription will remain active until the end of the current billing period.
    """
    subscription = await subscription_service.get_subscription_by_user_id(current_user.id)
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Subscription not found"}
        )
    
    if subscription.plan_id == PlanType.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "Cannot cancel free subscription"}
        )
    
    updated = await subscription_service.cancel_subscription(current_user.id)
    
    return APIResponse(
        success=True,
        data=CancelSubscriptionResponse(
            cancel_at_period_end=updated.cancel_at_period_end,
            current_period_end=updated.current_period_end,
        )
    )


@router.post("/me/reactivate", response_model=APIResponse[SubscriptionResponse])
async def reactivate_subscription(
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Reactivate a cancelled subscription.
    
    Only works if the subscription hasn't expired yet.
    """
    subscription = await subscription_service.get_subscription_by_user_id(current_user.id)
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Subscription not found"}
        )
    
    if not subscription.cancel_at_period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "Subscription is not cancelled"}
        )
    
    updated = await subscription_service.reactivate_subscription(current_user.id)
    
    return APIResponse(
        success=True,
        data=SubscriptionResponse.from_subscription(updated)
    )


@router.post("/{subscription_id}/cancel", response_model=APIResponse[CancelSubscriptionResponse])
async def cancel_subscription_by_id(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Cancel a specific subscription by ID.
    
    Users can only cancel their own subscription.
    """
    subscription = await subscription_service.get_subscription_by_user_id(current_user.id)
    
    if not subscription or subscription.id != subscription_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Subscription not found"}
        )
    
    if subscription.plan_id == PlanType.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "Cannot cancel free subscription"}
        )
    
    updated = await subscription_service.cancel_subscription(current_user.id)
    
    return APIResponse(
        success=True,
        data=CancelSubscriptionResponse(
            cancel_at_period_end=updated.cancel_at_period_end,
            current_period_end=updated.current_period_end,
        )
    )

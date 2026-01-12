"""Credits router for credits and batch tokens management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..models.credits import (
    CreditsResponse,
    BatchTokensResponse,
    UseCreditsResponse,
    UseBatchTokenResponse,
    RefillBatchTokensResponse,
)
from ..models.common import APIResponse
from ..models.user import User
from ..services.credits_service import CreditsService
from ..utils.exceptions import InsufficientCreditsError, InsufficientBatchTokensError
from .deps import get_credits_service, get_current_user, verify_api_key


router = APIRouter(prefix="/credits", tags=["Credits"])


# ========================
# Credits Endpoints
# ========================

@router.get("/me", response_model=APIResponse[CreditsResponse])
async def get_current_credits(
    current_user: User = Depends(get_current_user),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Get current user's credit balance.
    """
    credits = await credits_service.get_credits_response(current_user.id)
    
    if not credits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Credits not found"}
        )
    
    return APIResponse(success=True, data=credits)


@router.get("/user/{user_id}", response_model=APIResponse[CreditsResponse])
async def get_user_credits(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Get credits for a specific user.
    
    Users can only view their own credits.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot view other users' credits"}
        )
    
    credits = await credits_service.get_credits_response(user_id)
    
    if not credits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Credits not found"}
        )
    
    return APIResponse(success=True, data=credits)


class UseCreditsRequest(BaseModel):
    """Request to use credits (for internal use)."""
    user_id: UUID


@router.post("/use", response_model=APIResponse[UseCreditsResponse])
async def use_credit(
    request: UseCreditsRequest,
    _: bool = Depends(verify_api_key),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Use one credit for generation.
    
    This endpoint is for internal use (API key required).
    """
    try:
        result = await credits_service.use_credit(request.user_id)
        
        return APIResponse(
            success=True,
            data=UseCreditsResponse(
                generations_used=result.generations_used,
                generations_limit=result.generations_limit,
                remaining=result.remaining,
            )
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message}
        )


# ========================
# Batch Tokens Endpoints
# ========================

@router.get("/batch-tokens/me", response_model=APIResponse[BatchTokensResponse])
async def get_current_batch_tokens(
    current_user: User = Depends(get_current_user),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Get current user's batch token balance.
    """
    tokens = await credits_service.get_batch_tokens_response(current_user.id)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Batch tokens not found"}
        )
    
    return APIResponse(success=True, data=tokens)


@router.get("/batch-tokens/user/{user_id}", response_model=APIResponse[BatchTokensResponse])
async def get_user_batch_tokens(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Get batch tokens for a specific user.
    
    Users can only view their own batch tokens.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot view other users' batch tokens"}
        )
    
    tokens = await credits_service.get_batch_tokens_response(user_id)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Batch tokens not found"}
        )
    
    return APIResponse(success=True, data=tokens)


class UseBatchTokenRequest(BaseModel):
    """Request to use batch token (for internal use)."""
    user_id: UUID


@router.post("/batch-tokens/use", response_model=APIResponse[UseBatchTokenResponse])
async def use_batch_token(
    request: UseBatchTokenRequest,
    _: bool = Depends(verify_api_key),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Use one batch token for scheduled generation.
    
    This endpoint is for internal use (API key required).
    """
    try:
        result = await credits_service.use_batch_token(request.user_id)
        return APIResponse(success=True, data=result)
    except InsufficientBatchTokensError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message}
        )


class RefillBatchTokensRequest(BaseModel):
    """Request to refill batch tokens (for internal use)."""
    user_id: UUID
    plan_id: str


@router.post("/batch-tokens/refill", response_model=APIResponse[RefillBatchTokensResponse])
async def refill_batch_tokens(
    request: RefillBatchTokensRequest,
    _: bool = Depends(verify_api_key),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Refill batch tokens based on plan.
    
    This endpoint is for internal use (API key required).
    Called when user upgrades/subscribes to a plan.
    """
    from ..models.subscription import PlanType
    
    try:
        plan_id = PlanType(request.plan_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": f"Invalid plan: {request.plan_id}"}
        )
    
    result = await credits_service.refill_batch_tokens(request.user_id, plan_id)
    return APIResponse(success=True, data=result)

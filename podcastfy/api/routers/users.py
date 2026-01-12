"""Users router for user management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.user import User, UserUpdate, UserResponse, UserWithStats
from ..models.common import APIResponse, SuccessResponse
from ..services.user_service import UserService
from .deps import get_user_service, get_current_user


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's profile.
    """
    return APIResponse(
        success=True,
        data=UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            picture=current_user.picture,
            created_at=current_user.created_at,
        )
    )


@router.get("/me/stats", response_model=APIResponse[UserWithStats])
async def get_current_user_stats(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    Get current user's profile with subscription and usage statistics.
    """
    stats = await user_service.get_user_with_stats(current_user.id)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "User stats not found"}
        )
    
    return APIResponse(success=True, data=stats)


@router.patch("/me", response_model=APIResponse[UserResponse])
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    Update current user's profile.
    
    Only name and picture can be updated.
    """
    updated_user = await user_service.update_user(current_user.id, user_data)
    
    return APIResponse(
        success=True,
        data=UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            name=updated_user.name,
            picture=updated_user.picture,
            created_at=updated_user.created_at,
        )
    )


@router.delete("/me", response_model=SuccessResponse)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    Delete current user's account.
    
    This action is irreversible and will delete all associated data.
    """
    await user_service.delete_user(current_user.id)
    return SuccessResponse(success=True, message="Account deleted successfully")


@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user_by_id(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    Get user by ID.
    
    Users can only view their own profile.
    """
    # Users can only view their own profile
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot view other users' profiles"}
        )
    
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "User not found"}
        )
    
    return APIResponse(
        success=True,
        data=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            picture=user.picture,
            created_at=user.created_at,
        )
    )

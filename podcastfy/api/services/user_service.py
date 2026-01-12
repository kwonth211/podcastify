"""User service for user management operations."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from supabase import Client

from ..models.user import User, UserCreate, UserUpdate, UserWithStats
from ..utils.exceptions import NotFoundError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class UserService:
    """Service for user-related operations."""
    
    def __init__(self, db: Client):
        self.db = db
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = self.db.table("users").select("*").eq(
            "id", str(user_id)
        ).execute()
        
        if not result.data:
            return None
        
        return User(**result.data[0])
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = self.db.table("users").select("*").eq(
            "email", email
        ).execute()
        
        if not result.data:
            return None
        
        return User(**result.data[0])
    
    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID."""
        result = self.db.table("users").select("*").eq(
            "google_id", google_id
        ).execute()
        
        if not result.data:
            return None
        
        return User(**result.data[0])
    
    async def get_user_by_supabase_auth_id(self, auth_id: UUID) -> Optional[User]:
        """Get user by Supabase Auth ID."""
        result = self.db.table("users").select("*").eq(
            "supabase_auth_id", str(auth_id)
        ).execute()
        
        if not result.data:
            return None
        
        return User(**result.data[0])
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        insert_data = {
            "email": user_data.email,
            "name": user_data.name,
            "picture": user_data.picture,
        }
        
        if user_data.google_id:
            insert_data["google_id"] = user_data.google_id
        
        if user_data.supabase_auth_id:
            insert_data["supabase_auth_id"] = str(user_data.supabase_auth_id)
        
        result = self.db.table("users").insert(insert_data).execute()
        
        if not result.data:
            raise Exception("Failed to create user")
        
        logger.info(f"Created user: {result.data[0]['id']}")
        return User(**result.data[0])
    
    async def update_user(self, user_id: UUID, user_data: UserUpdate) -> User:
        """Update user data."""
        update_data = user_data.model_dump(exclude_unset=True)
        
        if not update_data:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise NotFoundError("User", str(user_id))
            return user
        
        result = self.db.table("users").update(update_data).eq(
            "id", str(user_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("User", str(user_id))
        
        logger.info(f"Updated user: {user_id}")
        return User(**result.data[0])
    
    async def delete_user(self, user_id: UUID) -> bool:
        """Delete user (cascades to all related data)."""
        result = self.db.table("users").delete().eq(
            "id", str(user_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("User", str(user_id))
        
        logger.info(f"Deleted user: {user_id}")
        return True
    
    async def get_user_with_stats(self, user_id: UUID) -> Optional[UserWithStats]:
        """Get user with subscription and usage statistics."""
        result = self.db.table("user_stats").select("*").eq(
            "id", str(user_id)
        ).execute()
        
        if not result.data:
            return None
        
        data = result.data[0]
        return UserWithStats(
            id=UUID(data["id"]),
            email=data["email"],
            name=data["name"],
            picture=data.get("picture"),
            created_at=datetime.fromisoformat(data["created_at"]),
            plan_id=data.get("plan_id", "free"),
            subscription_status=data.get("subscription_status", "active"),
            generations_used=data.get("generations_used", 0),
            generations_limit=data.get("generations_limit", 1),
            batch_tokens_remaining=data.get("batch_tokens_remaining", 0),
            active_schedules=data.get("active_schedules", 0),
            total_podcasts=data.get("total_podcasts", 0),
        )
    
    async def list_users(
        self, 
        limit: int = 50, 
        offset: int = 0
    ) -> tuple[List[User], int]:
        """List users with pagination (admin only)."""
        # Get total count
        count_result = self.db.table("users").select(
            "*", count="exact"
        ).execute()
        total = count_result.count or 0
        
        # Get paginated results
        result = self.db.table("users").select("*").range(
            offset, offset + limit - 1
        ).order("created_at", desc=True).execute()
        
        users = [User(**row) for row in result.data]
        return users, total

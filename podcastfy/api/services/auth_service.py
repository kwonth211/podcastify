"""Authentication service using Supabase Auth."""

import os
from typing import Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID

import jwt
from supabase import Client

from ..models.auth import AuthResponse, AuthUserInfo, TokenPayload
from ..models.user import User
from ..db import get_supabase_admin_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations."""
    
    JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("SUPABASE_JWT_SECRET", ""))
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS = 24
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    def __init__(self, db: Client):
        self.db = db
        self._admin_db: Optional[Client] = None
    
    @property
    def admin_db(self) -> Client:
        """Get admin database client (lazy load)."""
        if self._admin_db is None:
            self._admin_db = get_supabase_admin_client()
        return self._admin_db
    
    async def authenticate_with_google(
        self, 
        code: str, 
        redirect_uri: str
    ) -> AuthResponse:
        """
        Authenticate user with Google OAuth code.
        
        Uses Supabase Auth to handle the OAuth flow.
        """
        try:
            # Exchange code for session using Supabase Auth
            # Note: For production, you should use Supabase's built-in OAuth
            # This is a simplified example
            
            # Get user from Supabase auth
            auth_response = self.db.auth.sign_in_with_oauth({
                "provider": "google",
            })
            
            # For direct code exchange, use the admin client
            # This requires setting up the OAuth credentials in Supabase dashboard
            
            raise NotImplementedError(
                "Use Supabase Auth UI or redirect flow for Google OAuth. "
                "Configure Google OAuth in your Supabase project settings."
            )
            
        except Exception as e:
            logger.error(f"Google authentication failed: {e}")
            raise
    
    async def get_or_create_user_from_auth(
        self, 
        supabase_auth_id: UUID,
        email: str,
        name: str,
        picture: Optional[str] = None,
        google_id: Optional[str] = None
    ) -> User:
        """Get or create user from Supabase Auth data."""
        try:
            # Check if user exists
            result = self.admin_db.table("users").select("*").eq(
                "supabase_auth_id", str(supabase_auth_id)
            ).execute()
            
            if result.data:
                # Update existing user
                user_data = result.data[0]
                self.admin_db.table("users").update({
                    "email": email,
                    "name": name,
                    "picture": picture,
                    "google_id": google_id,
                }).eq("id", user_data["id"]).execute()
                
                # Refresh user data
                result = self.admin_db.table("users").select("*").eq(
                    "id", user_data["id"]
                ).execute()
                user_data = result.data[0]
            else:
                # Create new user
                insert_result = self.admin_db.table("users").insert({
                    "supabase_auth_id": str(supabase_auth_id),
                    "email": email,
                    "name": name,
                    "picture": picture,
                    "google_id": google_id,
                }).execute()
                user_data = insert_result.data[0]
            
            return User(**user_data)
            
        except Exception as e:
            logger.error(f"Failed to get/create user: {e}")
            raise
    
    def create_access_token(self, user: User) -> str:
        """Create JWT access token."""
        now = datetime.utcnow()
        expire = now + timedelta(hours=self.ACCESS_TOKEN_EXPIRE_HOURS)
        
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "iat": now,
            "exp": expire,
            "type": "access",
        }
        
        return jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
    
    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token."""
        now = datetime.utcnow()
        expire = now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "iat": now,
            "exp": expire,
            "type": "refresh",
        }
        
        return jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
    
    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token, 
                self.JWT_SECRET, 
                algorithms=[self.JWT_ALGORITHM]
            )
            return TokenPayload(
                sub=payload["sub"],
                email=payload["email"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
                type=payload.get("type", "access"),
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh access token using refresh token."""
        payload = self.verify_token(refresh_token)
        
        if not payload or payload.type != "refresh":
            return None
        
        # Get user from database
        result = self.admin_db.table("users").select("*").eq(
            "id", payload.sub
        ).execute()
        
        if not result.data:
            return None
        
        user = User(**result.data[0])
        return self.create_access_token(user)
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = self.admin_db.table("users").select("*").eq(
            "id", str(user_id)
        ).execute()
        
        if not result.data:
            return None
        
        return User(**result.data[0])
    
    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from token."""
        payload = self.verify_token(token)
        
        if not payload or payload.type != "access":
            return None
        
        return await self.get_user_by_id(UUID(payload.sub))

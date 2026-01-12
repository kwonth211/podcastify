"""Credits and batch tokens service."""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from supabase import Client

from ..models.credits import (
    Credits,
    CreditsResponse,
    BatchTokens,
    BatchTokensResponse,
    UseBatchTokenResponse,
    RefillBatchTokensResponse,
)
from ..models.subscription import PlanType, PLAN_CONFIGS
from ..utils.exceptions import (
    NotFoundError, 
    InsufficientCreditsError,
    InsufficientBatchTokensError,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CreditsService:
    """Service for credits and batch tokens operations."""
    
    def __init__(self, db: Client):
        self.db = db
    
    # ========================
    # Credits Methods
    # ========================
    
    async def get_credits_by_user_id(self, user_id: UUID) -> Optional[Credits]:
        """Get credits for a user."""
        result = self.db.table("credits").select("*").eq(
            "user_id", str(user_id)
        ).execute()
        
        if not result.data:
            return None
        
        return Credits(**result.data[0])
    
    async def get_credits_response(self, user_id: UUID) -> Optional[CreditsResponse]:
        """Get credits response with remaining calculation."""
        credits = await self.get_credits_by_user_id(user_id)
        if not credits:
            return None
        
        return CreditsResponse.from_credits(credits)
    
    async def use_credit(self, user_id: UUID) -> CreditsResponse:
        """Use one credit for generation."""
        credits = await self.get_credits_by_user_id(user_id)
        if not credits:
            raise NotFoundError("Credits", str(user_id))
        
        # Check if user has unlimited credits (Pro plan)
        if credits.generations_limit == -1:
            # Unlimited - just increment used for tracking
            result = self.db.table("credits").update({
                "generations_used": credits.generations_used + 1,
            }).eq("user_id", str(user_id)).execute()
        else:
            # Check if credits remaining
            remaining = credits.generations_limit - credits.generations_used
            if remaining <= 0:
                raise InsufficientCreditsError(remaining=0)
            
            result = self.db.table("credits").update({
                "generations_used": credits.generations_used + 1,
            }).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            raise NotFoundError("Credits", str(user_id))
        
        logger.info(f"Used credit for user {user_id}")
        return CreditsResponse.from_credits(Credits(**result.data[0]))
    
    async def reset_credits(
        self, 
        user_id: UUID, 
        new_limit: Optional[int] = None
    ) -> Credits:
        """Reset credits for a new period."""
        now = datetime.utcnow()
        next_reset = now + timedelta(days=30)
        
        update_data = {
            "generations_used": 0,
            "reset_date": next_reset.isoformat(),
        }
        
        if new_limit is not None:
            update_data["generations_limit"] = new_limit
        
        result = self.db.table("credits").update(update_data).eq(
            "user_id", str(user_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Credits", str(user_id))
        
        logger.info(f"Reset credits for user {user_id}")
        return Credits(**result.data[0])
    
    async def update_credits_limit(self, user_id: UUID, plan_id: PlanType) -> Credits:
        """Update credits limit based on plan."""
        plan_config = PLAN_CONFIGS.get(plan_id, PLAN_CONFIGS[PlanType.FREE])
        
        result = self.db.table("credits").update({
            "generations_limit": plan_config.generations_per_month,
            "generations_used": 0,
            "reset_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        }).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            raise NotFoundError("Credits", str(user_id))
        
        logger.info(f"Updated credits limit for user {user_id} to {plan_config.generations_per_month}")
        return Credits(**result.data[0])
    
    # ========================
    # Batch Tokens Methods
    # ========================
    
    async def get_batch_tokens_by_user_id(self, user_id: UUID) -> Optional[BatchTokens]:
        """Get batch tokens for a user."""
        result = self.db.table("batch_tokens").select("*").eq(
            "user_id", str(user_id)
        ).execute()
        
        if not result.data:
            return None
        
        return BatchTokens(**result.data[0])
    
    async def get_batch_tokens_response(self, user_id: UUID) -> Optional[BatchTokensResponse]:
        """Get batch tokens response."""
        tokens = await self.get_batch_tokens_by_user_id(user_id)
        if not tokens:
            return None
        
        return BatchTokensResponse.from_batch_tokens(tokens)
    
    async def use_batch_token(self, user_id: UUID) -> UseBatchTokenResponse:
        """Use one batch token for scheduled generation."""
        tokens = await self.get_batch_tokens_by_user_id(user_id)
        if not tokens:
            raise NotFoundError("Batch tokens", str(user_id))
        
        # Check if tokens are unlimited (Pro plan)
        if tokens.tokens_total == -1:
            # Unlimited - no decrement needed, just return current state
            return UseBatchTokenResponse(
                tokens_remaining=-1,
                tokens_total=-1,
                valid_until=tokens.valid_until,
            )
        
        # Check if expired
        now = datetime.utcnow()
        if now > tokens.valid_until.replace(tzinfo=None):
            raise InsufficientBatchTokensError(
                message="Batch tokens have expired.",
                remaining=0,
            )
        
        # Check if tokens remaining
        if tokens.tokens_remaining <= 0:
            raise InsufficientBatchTokensError(remaining=0)
        
        result = self.db.table("batch_tokens").update({
            "tokens_remaining": tokens.tokens_remaining - 1,
        }).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            raise NotFoundError("Batch tokens", str(user_id))
        
        updated = BatchTokens(**result.data[0])
        logger.info(f"Used batch token for user {user_id}, remaining: {updated.tokens_remaining}")
        
        return UseBatchTokenResponse(
            tokens_remaining=updated.tokens_remaining,
            tokens_total=updated.tokens_total,
            valid_until=updated.valid_until,
        )
    
    async def refill_batch_tokens(
        self, 
        user_id: UUID, 
        plan_id: PlanType
    ) -> RefillBatchTokensResponse:
        """Refill batch tokens based on plan."""
        plan_config = PLAN_CONFIGS.get(plan_id, PLAN_CONFIGS[PlanType.FREE])
        
        now = datetime.utcnow()
        
        # Calculate validity
        if plan_config.batch_token_validity_days == -1:
            # Pro plan - set far future date
            valid_until = now + timedelta(days=36500)  # ~100 years
        else:
            valid_until = now + timedelta(days=plan_config.batch_token_validity_days)
        
        tokens_total = plan_config.batch_tokens
        
        result = self.db.table("batch_tokens").update({
            "tokens_remaining": tokens_total,
            "tokens_total": tokens_total,
            "valid_until": valid_until.isoformat(),
        }).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            raise NotFoundError("Batch tokens", str(user_id))
        
        logger.info(f"Refilled batch tokens for user {user_id}: {tokens_total} tokens")
        
        return RefillBatchTokensResponse(
            tokens_remaining=tokens_total,
            tokens_total=tokens_total,
            valid_until=valid_until,
        )
    
    async def check_batch_token_availability(self, user_id: UUID) -> bool:
        """Check if user has available batch tokens."""
        tokens = await self.get_batch_tokens_by_user_id(user_id)
        if not tokens:
            return False
        
        # Unlimited tokens
        if tokens.tokens_total == -1:
            return True
        
        # Check expiry
        now = datetime.utcnow()
        if now > tokens.valid_until.replace(tzinfo=None):
            return False
        
        return tokens.tokens_remaining > 0
    
    async def check_expired_credits(self) -> int:
        """Check and reset expired credits."""
        now = datetime.utcnow()
        
        result = self.db.table("credits").select("*").lt(
            "reset_date", now.isoformat()
        ).execute()
        
        count = 0
        for row in result.data:
            try:
                await self.reset_credits(UUID(row["user_id"]))
                count += 1
            except Exception as e:
                logger.error(f"Failed to reset credits: {e}")
        
        logger.info(f"Reset {count} expired credits")
        return count

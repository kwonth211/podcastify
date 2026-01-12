"""Subscription service for plan management."""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from supabase import Client

from ..models.subscription import (
    Subscription, 
    SubscriptionResponse,
    SubscriptionStatus,
    PlanType,
    PLAN_CONFIGS,
)
from ..utils.exceptions import NotFoundError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SubscriptionService:
    """Service for subscription operations."""
    
    def __init__(self, db: Client):
        self.db = db
    
    async def get_subscription_by_user_id(self, user_id: UUID) -> Optional[Subscription]:
        """Get subscription for a user."""
        result = self.db.table("subscriptions").select("*").eq(
            "user_id", str(user_id)
        ).execute()
        
        if not result.data:
            return None
        
        return Subscription(**result.data[0])
    
    async def get_subscription_response(self, user_id: UUID) -> Optional[SubscriptionResponse]:
        """Get subscription response with features."""
        sub = await self.get_subscription_by_user_id(user_id)
        if not sub:
            return None
        
        return SubscriptionResponse.from_subscription(sub)
    
    async def create_subscription(
        self,
        user_id: UUID,
        plan_id: PlanType = PlanType.FREE
    ) -> Subscription:
        """Create a new subscription for a user."""
        plan_config = PLAN_CONFIGS.get(plan_id, PLAN_CONFIGS[PlanType.FREE])
        
        now = datetime.utcnow()
        
        # Calculate period end based on plan
        if plan_id == PlanType.FREE:
            period_end = now + timedelta(days=365)  # Free plan is effectively forever
        else:
            period_end = now + timedelta(days=30)
        
        insert_data = {
            "user_id": str(user_id),
            "plan_id": plan_id.value,
            "status": SubscriptionStatus.ACTIVE.value,
            "current_period_start": now.isoformat(),
            "current_period_end": period_end.isoformat(),
        }
        
        result = self.db.table("subscriptions").insert(insert_data).execute()
        
        if not result.data:
            raise Exception("Failed to create subscription")
        
        logger.info(f"Created subscription for user {user_id} with plan {plan_id}")
        return Subscription(**result.data[0])
    
    async def upgrade_subscription(
        self,
        user_id: UUID,
        new_plan_id: PlanType,
        stripe_subscription_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        toss_subscription_id: Optional[str] = None,
        toss_customer_key: Optional[str] = None,
    ) -> Subscription:
        """Upgrade user's subscription to a new plan."""
        existing = await self.get_subscription_by_user_id(user_id)
        if not existing:
            raise NotFoundError("Subscription", str(user_id))
        
        now = datetime.utcnow()
        period_end = now + timedelta(days=30)
        
        update_data = {
            "plan_id": new_plan_id.value,
            "status": SubscriptionStatus.ACTIVE.value,
            "current_period_start": now.isoformat(),
            "current_period_end": period_end.isoformat(),
            "cancel_at_period_end": False,
        }
        
        if stripe_subscription_id:
            update_data["stripe_subscription_id"] = stripe_subscription_id
        if stripe_customer_id:
            update_data["stripe_customer_id"] = stripe_customer_id
        if toss_subscription_id:
            update_data["toss_subscription_id"] = toss_subscription_id
        if toss_customer_key:
            update_data["toss_customer_key"] = toss_customer_key
        
        result = self.db.table("subscriptions").update(update_data).eq(
            "user_id", str(user_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Subscription", str(user_id))
        
        logger.info(f"Upgraded subscription for user {user_id} to plan {new_plan_id}")
        return Subscription(**result.data[0])
    
    async def cancel_subscription(self, user_id: UUID) -> Subscription:
        """Cancel subscription at period end."""
        existing = await self.get_subscription_by_user_id(user_id)
        if not existing:
            raise NotFoundError("Subscription", str(user_id))
        
        result = self.db.table("subscriptions").update({
            "cancel_at_period_end": True,
        }).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            raise NotFoundError("Subscription", str(user_id))
        
        logger.info(f"Scheduled cancellation for user {user_id}")
        return Subscription(**result.data[0])
    
    async def reactivate_subscription(self, user_id: UUID) -> Subscription:
        """Reactivate a cancelled subscription."""
        existing = await self.get_subscription_by_user_id(user_id)
        if not existing:
            raise NotFoundError("Subscription", str(user_id))
        
        result = self.db.table("subscriptions").update({
            "cancel_at_period_end": False,
            "status": SubscriptionStatus.ACTIVE.value,
        }).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            raise NotFoundError("Subscription", str(user_id))
        
        logger.info(f"Reactivated subscription for user {user_id}")
        return Subscription(**result.data[0])
    
    async def handle_subscription_expired(self, user_id: UUID) -> Subscription:
        """Handle subscription expiration - downgrade to free."""
        result = self.db.table("subscriptions").update({
            "plan_id": PlanType.FREE.value,
            "status": SubscriptionStatus.ACTIVE.value,
            "cancel_at_period_end": False,
            "stripe_subscription_id": None,
            "toss_subscription_id": None,
        }).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            raise NotFoundError("Subscription", str(user_id))
        
        logger.info(f"Downgraded expired subscription for user {user_id} to free")
        return Subscription(**result.data[0])
    
    async def check_expired_subscriptions(self) -> int:
        """Check and process expired subscriptions."""
        now = datetime.utcnow()
        
        # Find expired subscriptions that should be cancelled
        result = self.db.table("subscriptions").select("*").eq(
            "cancel_at_period_end", True
        ).lt("current_period_end", now.isoformat()).execute()
        
        count = 0
        for row in result.data:
            try:
                await self.handle_subscription_expired(UUID(row["user_id"]))
                count += 1
            except Exception as e:
                logger.error(f"Failed to expire subscription: {e}")
        
        logger.info(f"Processed {count} expired subscriptions")
        return count

"""Subscription and plan models."""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class PlanType(str, Enum):
    """Plan type enumeration."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"


class PlanFeatures(BaseModel):
    """Plan features configuration."""
    plan_id: PlanType
    name: str
    price_usd: int = Field(..., description="Price in cents")
    price_krw: int = Field(..., description="Price in won")
    generations_per_month: int = Field(..., description="-1 for unlimited")
    scheduler_enabled: bool = True
    max_schedules: int = Field(..., description="-1 for unlimited")
    premium_voices: bool = False
    priority_crawling: bool = False
    rss_feed: bool = False
    batch_tokens: int = Field(..., description="-1 for unlimited")
    batch_token_validity_days: int = Field(..., description="-1 for no expiry")

    class Config:
        from_attributes = True


# Plan configuration constants
PLAN_CONFIGS = {
    PlanType.FREE: PlanFeatures(
        plan_id=PlanType.FREE,
        name="Free",
        price_usd=0,
        price_krw=0,
        generations_per_month=1,
        scheduler_enabled=True,
        max_schedules=-1,
        premium_voices=False,
        priority_crawling=False,
        rss_feed=False,
        batch_tokens=7,
        batch_token_validity_days=7,
    ),
    PlanType.BASIC: PlanFeatures(
        plan_id=PlanType.BASIC,
        name="Basic",
        price_usd=100,
        price_krw=1500,
        generations_per_month=3,
        scheduler_enabled=True,
        max_schedules=-1,
        premium_voices=False,
        priority_crawling=False,
        rss_feed=False,
        batch_tokens=30,
        batch_token_validity_days=30,
    ),
    PlanType.PRO: PlanFeatures(
        plan_id=PlanType.PRO,
        name="Pro",
        price_usd=1000,
        price_krw=15000,
        generations_per_month=-1,
        scheduler_enabled=True,
        max_schedules=-1,
        premium_voices=True,
        priority_crawling=True,
        rss_feed=True,
        batch_tokens=-1,
        batch_token_validity_days=-1,
    ),
}


class SubscriptionBase(BaseModel):
    """Base subscription model."""
    plan_id: PlanType = PlanType.FREE
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE


class Subscription(SubscriptionBase):
    """Full subscription model."""
    id: UUID
    user_id: UUID
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    toss_subscription_id: Optional[str] = None
    toss_customer_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """Subscription response for API."""
    id: UUID
    user_id: UUID
    plan_id: PlanType
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    features: Optional[PlanFeatures] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_subscription(cls, sub: Subscription) -> "SubscriptionResponse":
        """Create response with plan features included."""
        features = PLAN_CONFIGS.get(sub.plan_id)
        return cls(
            id=sub.id,
            user_id=sub.user_id,
            plan_id=sub.plan_id,
            status=sub.status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            features=features,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )


class CancelSubscriptionResponse(BaseModel):
    """Response for subscription cancellation."""
    cancel_at_period_end: bool = True
    current_period_end: datetime

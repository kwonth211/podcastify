"""Payment models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from enum import Enum

from .subscription import PlanType


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentProvider(str, Enum):
    """Payment provider enumeration."""
    STRIPE = "stripe"
    TOSS = "toss"


class PaymentBase(BaseModel):
    """Base payment model."""
    plan_id: PlanType
    amount: int = Field(..., description="Amount in smallest currency unit")
    currency: str = Field(default="KRW", pattern="^(USD|KRW)$")


class Payment(PaymentBase):
    """Full payment model."""
    id: UUID
    user_id: UUID
    provider: PaymentProvider
    provider_payment_id: Optional[str] = None
    provider_order_id: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDING
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    """Payment response for API."""
    id: UUID
    user_id: UUID
    plan_id: PlanType
    amount: int
    currency: str
    provider: PaymentProvider
    status: PaymentStatus
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Stripe Models
class StripeCheckoutRequest(BaseModel):
    """Request for Stripe checkout session creation."""
    plan_id: PlanType
    success_url: str = Field(
        ...,
        description="URL to redirect on success. Use {CHECKOUT_SESSION_ID} placeholder."
    )
    cancel_url: str = Field(..., description="URL to redirect on cancel")


class StripeCheckoutResponse(BaseModel):
    """Response for Stripe checkout session."""
    session_id: str
    url: str


class StripeWebhookEvent(BaseModel):
    """Stripe webhook event model."""
    id: str
    type: str
    data: Dict[str, Any]


# Toss Models
class TossConfirmRequest(BaseModel):
    """Request to confirm Toss payment."""
    payment_key: str = Field(..., description="Toss payment key")
    order_id: str = Field(..., description="Order ID")
    amount: int = Field(..., description="Payment amount")


class TossConfirmResponse(BaseModel):
    """Response for Toss payment confirmation."""
    payment_key: str
    order_id: str
    status: str
    total_amount: int
    method: str
    approved_at: datetime


class TossWebhookEvent(BaseModel):
    """Toss webhook event model."""
    event_type: str
    data: Dict[str, Any]


# Payment History
class PaymentHistoryResponse(BaseModel):
    """Response for payment history."""
    payments: List[PaymentResponse]
    total: int

"""Pydantic models for API request/response schemas."""

from .user import User, UserCreate, UserUpdate, UserResponse
from .subscription import (
    Subscription,
    SubscriptionResponse,
    SubscriptionStatus,
    PlanType,
    PlanFeatures,
)
from .credits import Credits, CreditsResponse, BatchTokens, BatchTokensResponse
from .schedule import (
    Schedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    DayOfWeek,
)
from .podcast import (
    Podcast,
    PodcastCreate,
    PodcastResponse,
    PodcastStatus,
    PodcastGenerateRequest,
    PodcastStatusResponse,
)
from .payment import (
    Payment,
    PaymentStatus,
    PaymentProvider,
    StripeCheckoutRequest,
    StripeCheckoutResponse,
    TossConfirmRequest,
    TossConfirmResponse,
    PaymentHistoryResponse,
)
from .auth import (
    GoogleAuthRequest,
    AuthResponse,
    TokenPayload,
    RefreshTokenRequest,
)
from .common import (
    APIResponse,
    PaginatedResponse,
    ErrorResponse,
    SuccessResponse,
)

__all__ = [
    # User
    "User",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    # Subscription
    "Subscription",
    "SubscriptionResponse",
    "SubscriptionStatus",
    "PlanType",
    "PlanFeatures",
    # Credits
    "Credits",
    "CreditsResponse",
    "BatchTokens",
    "BatchTokensResponse",
    # Schedule
    "Schedule",
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleResponse",
    "DayOfWeek",
    # Podcast
    "Podcast",
    "PodcastCreate",
    "PodcastResponse",
    "PodcastStatus",
    "PodcastGenerateRequest",
    "PodcastStatusResponse",
    # Payment
    "Payment",
    "PaymentStatus",
    "PaymentProvider",
    "StripeCheckoutRequest",
    "StripeCheckoutResponse",
    "TossConfirmRequest",
    "TossConfirmResponse",
    "PaymentHistoryResponse",
    # Auth
    "GoogleAuthRequest",
    "AuthResponse",
    "TokenPayload",
    "RefreshTokenRequest",
    # Common
    "APIResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",
]

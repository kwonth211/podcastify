"""Credits and batch tokens models."""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class CreditsBase(BaseModel):
    """Base credits model."""
    generations_used: int = 0
    generations_limit: int = 1


class Credits(CreditsBase):
    """Full credits model."""
    id: UUID
    user_id: UUID
    reset_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreditsResponse(BaseModel):
    """Credits response for API."""
    user_id: UUID
    generations_used: int
    generations_limit: int
    remaining: int = Field(..., description="Remaining generations")
    reset_date: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_credits(cls, credits: Credits) -> "CreditsResponse":
        """Create response with calculated remaining."""
        remaining = max(0, credits.generations_limit - credits.generations_used)
        return cls(
            user_id=credits.user_id,
            generations_used=credits.generations_used,
            generations_limit=credits.generations_limit,
            remaining=remaining,
            reset_date=credits.reset_date,
        )


class UseCreditsRequest(BaseModel):
    """Request to use credits."""
    user_id: UUID


class UseCreditsResponse(BaseModel):
    """Response after using credits."""
    generations_used: int
    generations_limit: int
    remaining: int


class BatchTokensBase(BaseModel):
    """Base batch tokens model."""
    tokens_remaining: int = 0
    tokens_total: int = 0


class BatchTokens(BatchTokensBase):
    """Full batch tokens model."""
    id: UUID
    user_id: UUID
    valid_until: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchTokensResponse(BaseModel):
    """Batch tokens response for API."""
    user_id: UUID
    tokens_remaining: int
    tokens_total: int
    tokens_used: int = Field(..., description="Tokens already used")
    valid_until: datetime
    is_expired: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_batch_tokens(cls, bt: BatchTokens) -> "BatchTokensResponse":
        """Create response with calculated fields."""
        tokens_used = bt.tokens_total - bt.tokens_remaining
        is_expired = datetime.utcnow() > bt.valid_until.replace(tzinfo=None)
        return cls(
            user_id=bt.user_id,
            tokens_remaining=bt.tokens_remaining,
            tokens_total=bt.tokens_total,
            tokens_used=tokens_used,
            valid_until=bt.valid_until,
            is_expired=is_expired,
            created_at=bt.created_at,
            updated_at=bt.updated_at,
        )


class UseBatchTokenRequest(BaseModel):
    """Request to use a batch token."""
    user_id: UUID


class UseBatchTokenResponse(BaseModel):
    """Response after using a batch token."""
    tokens_remaining: int
    tokens_total: int
    valid_until: datetime


class RefillBatchTokensRequest(BaseModel):
    """Request to refill batch tokens."""
    user_id: UUID
    plan_id: str


class RefillBatchTokensResponse(BaseModel):
    """Response after refilling batch tokens."""
    tokens_remaining: int
    tokens_total: int
    valid_until: datetime

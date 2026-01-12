"""Custom exceptions for the API."""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class APIException(HTTPException):
    """Base API exception with error code support."""
    
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                **self.details
            }
        )


class NotFoundError(APIException):
    """Resource not found error."""
    
    def __init__(self, resource: str = "Resource", resource_id: Optional[str] = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with ID '{resource_id}' not found"
        
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=message,
        )


class UnauthorizedError(APIException):
    """Unauthorized access error."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=message,
        )


class ForbiddenError(APIException):
    """Forbidden access error."""
    
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=message,
        )


class BadRequestError(APIException):
    """Bad request error."""
    
    def __init__(self, message: str = "Bad request", field: Optional[str] = None):
        details = {}
        if field:
            details["field"] = field
        
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class InsufficientCreditsError(APIException):
    """Insufficient credits error."""
    
    def __init__(
        self, 
        message: str = "No credits remaining. Please upgrade your plan.",
        remaining: int = 0
    ):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code="INSUFFICIENT_CREDITS",
            message=message,
            details={"remaining": remaining},
        )


class InsufficientBatchTokensError(APIException):
    """Insufficient batch tokens error."""
    
    def __init__(
        self, 
        message: str = "No batch tokens remaining or expired. Please purchase a plan.",
        remaining: int = 0
    ):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code="INSUFFICIENT_BATCH_TOKENS",
            message=message,
            details={"remaining": remaining},
        )


class ScheduleLimitExceededError(APIException):
    """Schedule limit exceeded error."""
    
    def __init__(
        self, 
        message: str = "Schedule limit exceeded for your plan.",
        current: int = 0,
        limit: int = 0
    ):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code="SCHEDULE_LIMIT_EXCEEDED",
            message=message,
            details={"current": current, "limit": limit},
        )


class PlanFeatureDisabledError(APIException):
    """Plan feature disabled error."""
    
    def __init__(self, feature: str):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code="PLAN_FEATURE_DISABLED",
            message=f"This feature ({feature}) is not available in your current plan.",
            details={"feature": feature},
        )


class PaymentError(APIException):
    """Payment processing error."""
    
    def __init__(self, message: str = "Payment processing failed", provider: Optional[str] = None):
        details = {}
        if provider:
            details["provider"] = provider
        
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="PAYMENT_FAILED",
            message=message,
            details=details,
        )


class RateLimitError(APIException):
    """Rate limit exceeded error."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
            details={"retry_after": retry_after},
        )


class ServiceUnavailableError(APIException):
    """Service unavailable error."""
    
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SERVICE_UNAVAILABLE",
            message=message,
        )

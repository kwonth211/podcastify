"""Payments router for Stripe and Toss payment processing."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
import stripe
import os

from ..models.payment import (
    StripeCheckoutRequest,
    StripeCheckoutResponse,
    TossConfirmRequest,
    TossConfirmResponse,
    PaymentHistoryResponse,
)
from ..models.subscription import PlanType
from ..models.common import APIResponse, SuccessResponse
from ..models.user import User
from ..services.payment_service import PaymentService
from ..services.subscription_service import SubscriptionService
from ..services.credits_service import CreditsService
from ..utils.exceptions import PaymentError
from .deps import (
    get_payment_service,
    get_subscription_service,
    get_credits_service,
    get_current_user,
)


router = APIRouter(prefix="/payments", tags=["Payments"])


# ========================
# Stripe Endpoints
# ========================

@router.post("/stripe/checkout", response_model=APIResponse[StripeCheckoutResponse])
async def create_stripe_checkout(
    request: StripeCheckoutRequest,
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """
    Create a Stripe checkout session for subscription.
    
    Returns a checkout URL to redirect the user to.
    """
    try:
        result = await payment_service.create_stripe_checkout_session(
            user_id=current_user.id,
            plan_id=request.plan_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            email=current_user.email,
        )
        return APIResponse(success=True, data=result)
    except PaymentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    payment_service: PaymentService = Depends(get_payment_service),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Handle Stripe webhook events.
    
    Processes payment confirmations and subscription updates.
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()
    
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, webhook_secret
            )
        else:
            import json
            event = json.loads(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PAYLOAD", "message": str(e)}
        )
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_SIGNATURE", "message": str(e)}
        )
    
    # Process the event
    event_type = event.get("type") if isinstance(event, dict) else event.type
    event_data = event.get("data", {}) if isinstance(event, dict) else event.data
    
    if event_type == "checkout.session.completed":
        session = event_data.get("object", {}) if isinstance(event_data, dict) else event_data.object
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_id = metadata.get("plan_id")
        
        if user_id and plan_id:
            try:
                # Upgrade subscription
                await subscription_service.upgrade_subscription(
                    user_id=UUID(user_id),
                    new_plan_id=PlanType(plan_id),
                    stripe_subscription_id=session.get("subscription"),
                    stripe_customer_id=session.get("customer"),
                )
                
                # Refill batch tokens and credits
                await credits_service.refill_batch_tokens(
                    UUID(user_id), 
                    PlanType(plan_id)
                )
                await credits_service.update_credits_limit(
                    UUID(user_id), 
                    PlanType(plan_id)
                )
            except Exception as e:
                # Log error but don't fail webhook
                print(f"Error processing checkout: {e}")
    
    await payment_service.handle_stripe_webhook(
        event if isinstance(event, dict) else event.to_dict()
    )
    
    return SuccessResponse(success=True, message="Webhook processed")


# ========================
# Toss Endpoints
# ========================

@router.post("/toss/confirm", response_model=APIResponse[TossConfirmResponse])
async def confirm_toss_payment(
    request: TossConfirmRequest,
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    credits_service: CreditsService = Depends(get_credits_service),
):
    """
    Confirm a Toss payment after user completes payment.
    
    Called from the success redirect URL with paymentKey, orderId, and amount.
    """
    try:
        result = await payment_service.confirm_toss_payment(
            user_id=current_user.id,
            payment_key=request.payment_key,
            order_id=request.order_id,
            amount=request.amount,
        )
        
        # Extract plan_id from order_id (format: planId_userId_timestamp)
        parts = request.order_id.split("_")
        if parts:
            try:
                plan_id = PlanType(parts[0])
                
                # Upgrade subscription
                await subscription_service.upgrade_subscription(
                    user_id=current_user.id,
                    new_plan_id=plan_id,
                    toss_subscription_id=request.payment_key,
                )
                
                # Refill batch tokens and credits
                await credits_service.refill_batch_tokens(current_user.id, plan_id)
                await credits_service.update_credits_limit(current_user.id, plan_id)
            except ValueError:
                pass  # Invalid plan_id in order_id
        
        return APIResponse(success=True, data=result)
    except PaymentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.post("/webhook/toss")
async def toss_webhook(
    request: Request,
    payment_service: PaymentService = Depends(get_payment_service),
):
    """
    Handle Toss webhook events.
    
    Processes payment status changes and cancellations.
    """
    try:
        event = await request.json()
        await payment_service.handle_toss_webhook(event)
        return SuccessResponse(success=True, message="Webhook processed")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WEBHOOK_ERROR", "message": str(e)}
        )


# ========================
# Payment History
# ========================

@router.get("/history", response_model=APIResponse[PaymentHistoryResponse])
async def get_payment_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """
    Get payment history for current user.
    """
    result = await payment_service.get_payment_history(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return APIResponse(success=True, data=result)

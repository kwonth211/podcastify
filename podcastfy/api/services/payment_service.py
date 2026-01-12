"""Payment service for Stripe and Toss payments."""

import os
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from supabase import Client

from ..models.payment import (
    Payment,
    PaymentResponse,
    PaymentStatus,
    PaymentProvider,
    StripeCheckoutResponse,
    TossConfirmResponse,
    PaymentHistoryResponse,
)
from ..models.subscription import PlanType, PLAN_CONFIGS
from ..utils.exceptions import NotFoundError, PaymentError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PaymentService:
    """Service for payment operations."""
    
    def __init__(self, db: Client):
        self.db = db
        self._stripe = None
        self._toss_secret_key = os.getenv("TOSS_SECRET_KEY", "")
    
    @property
    def stripe(self):
        """Lazy load Stripe client."""
        if self._stripe is None:
            import stripe
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            self._stripe = stripe
        return self._stripe
    
    # ========================
    # Stripe Methods
    # ========================
    
    async def create_stripe_checkout_session(
        self,
        user_id: UUID,
        plan_id: PlanType,
        success_url: str,
        cancel_url: str,
        email: Optional[str] = None,
    ) -> StripeCheckoutResponse:
        """Create a Stripe checkout session."""
        if plan_id == PlanType.FREE:
            raise PaymentError("Cannot checkout for free plan", provider="stripe")
        
        plan_config = PLAN_CONFIGS.get(plan_id)
        if not plan_config:
            raise PaymentError(f"Invalid plan: {plan_id}", provider="stripe")
        
        try:
            # Get or create Stripe customer
            customer_data = {}
            if email:
                customer_data["customer_email"] = email
            
            # Create checkout session
            session = self.stripe.checkout.Session.create(
                mode="subscription" if plan_id == PlanType.PRO else "payment",
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Daily News Podcast - {plan_config.name} Plan",
                            "description": f"{'Unlimited' if plan_config.generations_per_month == -1 else plan_config.generations_per_month} generations per month",
                        },
                        "unit_amount": plan_config.price_usd,
                        "recurring": {"interval": "month"} if plan_id == PlanType.PRO else None,
                    },
                    "quantity": 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user_id),
                    "plan_id": plan_id.value,
                },
                **customer_data,
            )
            
            # Create payment record
            await self._create_payment_record(
                user_id=user_id,
                plan_id=plan_id,
                amount=plan_config.price_usd,
                currency="USD",
                provider=PaymentProvider.STRIPE,
                provider_payment_id=session.id,
            )
            
            logger.info(f"Created Stripe checkout session for user {user_id}")
            return StripeCheckoutResponse(
                session_id=session.id,
                url=session.url,
            )
            
        except Exception as e:
            logger.error(f"Stripe checkout error: {e}")
            raise PaymentError(str(e), provider="stripe")
    
    async def handle_stripe_webhook(self, event: dict) -> bool:
        """Handle Stripe webhook event."""
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        logger.info(f"Processing Stripe webhook: {event_type}")
        
        if event_type == "checkout.session.completed":
            return await self._handle_stripe_checkout_completed(data)
        elif event_type == "customer.subscription.updated":
            return await self._handle_stripe_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            return await self._handle_stripe_subscription_deleted(data)
        elif event_type == "invoice.payment_failed":
            return await self._handle_stripe_payment_failed(data)
        
        return True
    
    async def _handle_stripe_checkout_completed(self, data: dict) -> bool:
        """Handle successful checkout."""
        session_id = data.get("id")
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_id = metadata.get("plan_id")
        
        if not user_id or not plan_id:
            logger.error(f"Missing metadata in checkout session: {session_id}")
            return False
        
        # Update payment status
        await self._update_payment_status(
            provider_payment_id=session_id,
            status=PaymentStatus.COMPLETED,
        )
        
        # The subscription upgrade should be handled by the webhook handler
        # or by calling subscription_service.upgrade_subscription
        
        logger.info(f"Checkout completed for user {user_id}, plan {plan_id}")
        return True
    
    async def _handle_stripe_subscription_updated(self, data: dict) -> bool:
        """Handle subscription update."""
        # Handle subscription changes
        return True
    
    async def _handle_stripe_subscription_deleted(self, data: dict) -> bool:
        """Handle subscription cancellation."""
        # Handle subscription cancellation
        return True
    
    async def _handle_stripe_payment_failed(self, data: dict) -> bool:
        """Handle failed payment."""
        # Handle payment failure
        return True
    
    # ========================
    # Toss Methods
    # ========================
    
    async def confirm_toss_payment(
        self,
        user_id: UUID,
        payment_key: str,
        order_id: str,
        amount: int,
    ) -> TossConfirmResponse:
        """Confirm Toss payment."""
        import httpx
        import base64
        
        try:
            # Parse order_id to get plan_id
            parts = order_id.split("_")
            if len(parts) < 2:
                raise PaymentError("Invalid order ID format", provider="toss")
            
            plan_id_str = parts[0]
            try:
                plan_id = PlanType(plan_id_str)
            except ValueError:
                raise PaymentError(f"Invalid plan in order ID: {plan_id_str}", provider="toss")
            
            plan_config = PLAN_CONFIGS.get(plan_id)
            if not plan_config:
                raise PaymentError(f"Invalid plan: {plan_id}", provider="toss")
            
            # Verify amount
            if amount != plan_config.price_krw:
                raise PaymentError(
                    f"Amount mismatch: expected {plan_config.price_krw}, got {amount}",
                    provider="toss"
                )
            
            # Create auth header
            auth_string = f"{self._toss_secret_key}:"
            auth_header = base64.b64encode(auth_string.encode()).decode()
            
            # Confirm payment with Toss API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tosspayments.com/v1/payments/confirm",
                    headers={
                        "Authorization": f"Basic {auth_header}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "paymentKey": payment_key,
                        "orderId": order_id,
                        "amount": amount,
                    },
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    raise PaymentError(
                        error_data.get("message", "Payment confirmation failed"),
                        provider="toss"
                    )
                
                result = response.json()
            
            # Create payment record
            await self._create_payment_record(
                user_id=user_id,
                plan_id=plan_id,
                amount=amount,
                currency="KRW",
                provider=PaymentProvider.TOSS,
                provider_payment_id=payment_key,
                provider_order_id=order_id,
                status=PaymentStatus.COMPLETED,
            )
            
            logger.info(f"Toss payment confirmed for user {user_id}")
            
            return TossConfirmResponse(
                payment_key=result.get("paymentKey", payment_key),
                order_id=result.get("orderId", order_id),
                status=result.get("status", "DONE"),
                total_amount=result.get("totalAmount", amount),
                method=result.get("method", "카드"),
                approved_at=datetime.fromisoformat(
                    result.get("approvedAt", datetime.utcnow().isoformat()).replace("Z", "+00:00")
                ),
            )
            
        except PaymentError:
            raise
        except Exception as e:
            logger.error(f"Toss payment error: {e}")
            raise PaymentError(str(e), provider="toss")
    
    async def handle_toss_webhook(self, event: dict) -> bool:
        """Handle Toss webhook event."""
        event_type = event.get("eventType")
        data = event.get("data", {})
        
        logger.info(f"Processing Toss webhook: {event_type}")
        
        if event_type == "PAYMENT_STATUS_CHANGED":
            payment_key = data.get("paymentKey")
            status = data.get("status")
            
            if status == "CANCELED":
                await self._update_payment_status(
                    provider_payment_id=payment_key,
                    status=PaymentStatus.CANCELED,
                )
            elif status == "PARTIAL_CANCELED":
                await self._update_payment_status(
                    provider_payment_id=payment_key,
                    status=PaymentStatus.REFUNDED,
                )
        
        return True
    
    # ========================
    # Common Methods
    # ========================
    
    async def _create_payment_record(
        self,
        user_id: UUID,
        plan_id: PlanType,
        amount: int,
        currency: str,
        provider: PaymentProvider,
        provider_payment_id: Optional[str] = None,
        provider_order_id: Optional[str] = None,
        status: PaymentStatus = PaymentStatus.PENDING,
    ) -> Payment:
        """Create a payment record in database."""
        insert_data = {
            "user_id": str(user_id),
            "plan_id": plan_id.value,
            "amount": amount,
            "currency": currency,
            "provider": provider.value,
            "status": status.value,
        }
        
        if provider_payment_id:
            insert_data["provider_payment_id"] = provider_payment_id
        if provider_order_id:
            insert_data["provider_order_id"] = provider_order_id
        if status == PaymentStatus.COMPLETED:
            insert_data["paid_at"] = datetime.utcnow().isoformat()
        
        result = self.db.table("payments").insert(insert_data).execute()
        
        if not result.data:
            raise Exception("Failed to create payment record")
        
        return Payment(**result.data[0])
    
    async def _update_payment_status(
        self,
        provider_payment_id: str,
        status: PaymentStatus,
    ) -> Optional[Payment]:
        """Update payment status by provider ID."""
        update_data = {"status": status.value}
        
        if status == PaymentStatus.COMPLETED:
            update_data["paid_at"] = datetime.utcnow().isoformat()
        
        result = self.db.table("payments").update(update_data).eq(
            "provider_payment_id", provider_payment_id
        ).execute()
        
        if not result.data:
            logger.warning(f"Payment not found: {provider_payment_id}")
            return None
        
        return Payment(**result.data[0])
    
    async def get_payment_history(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> PaymentHistoryResponse:
        """Get payment history for a user."""
        result = self.db.table("payments").select("*", count="exact").eq(
            "user_id", str(user_id)
        ).order("created_at", desc=True).range(
            offset, offset + limit - 1
        ).execute()
        
        payments = [PaymentResponse(**row) for row in result.data]
        total = result.count or 0
        
        return PaymentHistoryResponse(
            payments=payments,
            total=total,
        )
    
    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        """Get payment by ID."""
        result = self.db.table("payments").select("*").eq(
            "id", str(payment_id)
        ).execute()
        
        if not result.data:
            return None
        
        return Payment(**result.data[0])

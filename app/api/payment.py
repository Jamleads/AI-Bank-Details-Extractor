"""
Payment API routes
"""
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_db
from app.models.user import UserDB
from app.models.payment import PaymentCreate, PaymentResponse, PricingTier
from app.utils.auth import get_current_user_required, get_user_id
from app.db import payment as payment_crud
from app.models.payment import PaymentStatus
from datetime import datetime
from pydantic import BaseModel
from app.services.yativo import yativo_service
from app.db.models import User as UserDBModel, SubscriptionTier

router = APIRouter()

# Define pricing tiers with amounts
PRICING = {
    PricingTier.FREE: 0,
    PricingTier.BASIC: 29,
    PricingTier.PRO: 79,
    PricingTier.ENTERPRISE: 199
}


class PaymentInitiateRequest(BaseModel):
    """Payment initiation request model"""
    tier: PricingTier
    country_code: str = "USA"


@router.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(
    request: PaymentInitiateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """Initiate a payment for a specific tier"""
    # Get tier and country code from request
    tier = request.tier
    country_code = request.country_code
    
    print(f"Initiating payment for tier: {tier}, country: {country_code}")
    
    # Get amount from pricing tier
    if tier not in PRICING:
        raise HTTPException(status_code=400, detail="Invalid pricing tier")
    
    amount = PRICING[tier]
    
    # Free tier doesn't need payment processing
    if amount == 0:
        # Create a completed payment record for tracking
        db_payment = await payment_crud.create_payment(db, get_user_id(current_user), 0, "USD", tier)
        await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.COMPLETED)
        
        # Update user's subscription tier
        await process_successful_payment(db_payment.id, db)
        
        return PaymentResponse(
            id=db_payment.id,
            amount=0,
            currency="USD",
            tier=tier,
            status=PaymentStatus.COMPLETED,
            created_at=db_payment.created_at
        )
    
    # Create initial payment record
    db_payment = await payment_crud.create_payment(db, get_user_id(current_user), amount, "USD", tier)
    
    # Get currencies supported for the country
    try:
        currencies = await yativo_service.get_payin_currencies(country_code)
        if not currencies:
            raise HTTPException(status_code=400, detail=f"No payment methods available for {country_code}")
        
        # Use USD if available, otherwise use first available currency
        currency = "USD" if "USD" in currencies else currencies[0]
        
        # Get payment gateways for the currency and country
        gateways = await yativo_service.get_payin_gateways(country_code, currency)
        if not gateways:
            raise HTTPException(status_code=400, detail=f"No payment gateways available for {country_code} and {currency}")
        
        # Use the first gateway (could be more sophisticated in production)
        gateway_id = gateways[0]["id"]
        
        # Create or get Yativo customer
        customer_data = await yativo_service.create_customer(
            user_id=str(get_user_id(current_user)),
            email=current_user.email,
            name=current_user.name
        )
        customer_id = customer_data.get("id")
        
        # Create deposit in Yativo
        deposit_data = await yativo_service.create_deposit(
            amount=amount,
            currency=currency,
            gateway_id=gateway_id,
            customer_id=customer_id
        )
        
        # Extract deposit ID and checkout URL
        deposit_id = deposit_data.get("id")
        checkout_url = deposit_data.get("checkout_url") or deposit_data.get("link")
        payment_method = f"Gateway_{gateway_id}"
        
        # Update payment record with Yativo details
        await payment_crud.update_payment_yativo_details(
            db,
            db_payment.id,
            yativo_deposit_id=deposit_id,
            yativo_customer_id=customer_id,
            checkout_url=checkout_url,
            payment_method=payment_method
        )
        
        # Return payment response with checkout URL
        return PaymentResponse(
            id=db_payment.id,
            amount=amount,
            currency=currency,
            tier=tier,
            status=PaymentStatus.PENDING,
            created_at=db_payment.created_at,
            checkout_url=checkout_url
        )
        
    except Exception as e:
        # Update payment status to failed
        await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.FAILED)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{payment_id}", response_model=PaymentResponse)
async def get_payment_status(
    payment_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """Get payment status"""
    db_payment = await payment_crud.get_payment(db, payment_id)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Check if this payment belongs to the current user
    if db_payment.user_id != get_user_id(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this payment")
    
    # If payment is pending and has a Yativo deposit ID, check status from Yativo
    if db_payment.status == PaymentStatus.PENDING.value and db_payment.yativo_deposit_id:
        try:
            transaction_data = await yativo_service.get_transaction(db_payment.yativo_deposit_id)
            status = transaction_data.get("status", "").lower()
            
            # Map Yativo status to our status
            if status in ("completed", "success"):
                await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.COMPLETED)
                db_payment.status = PaymentStatus.COMPLETED.value
                
                # Update user's subscription tier
                await process_successful_payment(db_payment.id, db)
                
            elif status in ("failed", "error"):
                await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.FAILED)
                db_payment.status = PaymentStatus.FAILED.value
            elif status == "expired":
                await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.EXPIRED)
                db_payment.status = PaymentStatus.EXPIRED.value
        except Exception:
            # If there's an error checking status, just return current status
            pass
    
    return PaymentResponse(
        id=db_payment.id,
        amount=db_payment.amount,
        currency=db_payment.currency,
        tier=PricingTier(db_payment.tier),
        status=PaymentStatus(db_payment.status),
        created_at=db_payment.created_at,
        checkout_url=db_payment.checkout_url
    )


@router.get("/history", response_model=List[PaymentResponse])
async def get_payment_history(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """Get payment history for current user"""
    payments = await payment_crud.get_payments_by_user(db, get_user_id(current_user))
    return [
        PaymentResponse(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            tier=PricingTier(payment.tier),
            status=PaymentStatus(payment.status),
            created_at=payment.created_at,
            checkout_url=payment.checkout_url
        )
        for payment in payments
    ]


@router.post("/webhook")
async def yativo_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """Webhook endpoint for Yativo payment notifications"""
    payload = await request.json()
    
    # Extract event type and data
    event_type = payload.get("event") or payload.get("events") or payload.get("type")
    data = payload.get("data", {})
    
    # Check if this is a deposit completion event
    deposit_id = data.get("id") or data.get("deposit_id")
    status = data.get("status", "").lower()
    
    if deposit_id and status:
        # Find payment by Yativo deposit ID
        db_payment = await payment_crud.get_payment_by_yativo_deposit_id(db, deposit_id)
        if db_payment:
            # Update payment status based on webhook data
            if status in ("completed", "success"):
                await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.COMPLETED)
                # Process the successful payment (update user subscription)
                background_tasks.add_task(process_successful_payment, db_payment.id, db)
            elif status in ("failed", "error"):
                await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.FAILED)
            elif status == "expired":
                await payment_crud.update_payment_status(db, db_payment.id, PaymentStatus.EXPIRED)
    
    # Always return success to acknowledge receipt of webhook
    return {"status": "success"}


async def process_successful_payment(payment_id: int, db: AsyncSession):
    """Process successful payment (grant access, send confirmation, etc.)"""
    # Get the payment
    db_payment = await payment_crud.get_payment(db, payment_id)
    if not db_payment:
        return
    
    # Get the user
    user = await db.query(UserDBModel).filter(UserDBModel.id == db_payment.user_id).first()
    if not user:
        return
    
    # Map PricingTier to SubscriptionTier
    tier_mapping = {
        PricingTier.FREE.value: SubscriptionTier.FREE,
        PricingTier.BASIC.value: SubscriptionTier.BASIC,
        PricingTier.PRO.value: SubscriptionTier.PRO,
        PricingTier.ENTERPRISE.value: SubscriptionTier.ENTERPRISE
    }
    
    # Update user's subscription tier
    if db_payment.tier in tier_mapping:
        user.subscription_tier = tier_mapping[db_payment.tier]
        user.subscription_updated_at = datetime.now()
        await db.commit()
    
    # Here you could also:
    # 1. Send confirmation email
    # 2. Log the subscription change
    # 3. Trigger any other business logic related to subscription changes


@router.get("/pricing")
async def get_pricing():
    """Get pricing information"""
    return {
        "free": {
            "price": 0,
            "features": [
                "Limited to 5 document uploads",
                "Basic bank details extraction",
                "CSV export"
            ]
        },
        "basic": {
            "price": PRICING[PricingTier.BASIC],
            "features": [
                "Up to 50 document uploads",
                "Advanced bank details extraction",
                "CSV and Excel exports",
                "Email support"
            ]
        },
        "pro": {
            "price": PRICING[PricingTier.PRO],
            "features": [
                "Up to 500 document uploads",
                "Advanced bank details extraction",
                "All export formats",
                "Priority email support",
                "Google Drive integration"
            ]
        },
        "enterprise": {
            "price": PRICING[PricingTier.ENTERPRISE],
            "features": [
                "Unlimited document uploads",
                "Advanced bank details extraction with custom fields",
                "All export formats",
                "Priority support",
                "Google Drive integration",
                "API access"
            ]
        }
    }
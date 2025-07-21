"""
Payment models for Yativo integration
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    """Payment status enum"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class PricingTier(str, Enum):
    """Pricing tier enum"""
    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class PaymentCreate(BaseModel):
    """Payment creation model"""
    user_id: int
    amount: float
    currency: str = "USD"
    tier: PricingTier
    country_code: str = "USA"  # Default to USA


class PaymentDB(BaseModel):
    """Payment database model"""
    id: int
    user_id: int
    yativo_deposit_id: Optional[str] = None
    yativo_customer_id: Optional[str] = None
    amount: float
    currency: str
    tier: PricingTier
    payment_method: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    """Payment response model"""
    id: int
    amount: float
    currency: str
    tier: PricingTier
    status: PaymentStatus
    created_at: datetime
    checkout_url: Optional[str] = None

    class Config:
        from_attributes = True


class YativoWebhookPayload(BaseModel):
    """Yativo webhook payload model"""
    event: str
    data: Dict[str, Any] 
"""
Payment database operations
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Session, relationship

from app.db.database import Base
from app.models.payment import PaymentDB, PaymentStatus, PricingTier
from app.db.adapter import db


class Payment(Base):
    """Payment table"""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    yativo_deposit_id = Column(String(255), nullable=True)
    yativo_customer_id = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    tier = Column(String(20), nullable=False)
    payment_method = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default=PaymentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    checkout_url = Column(Text, nullable=True)
    
    # Relationship with user
    user = relationship("User", back_populates="payments")


def create_payment(db_session: Session, user_id: int, amount: float, currency: str, tier: PricingTier) -> PaymentDB:
    """Create a new payment record"""
    return db.create_payment(user_id, amount, currency, tier.value)


def get_payment(db_session: Session, payment_id: int) -> Optional[Payment]:
    """Get payment by ID"""
    return db.get_payment(payment_id)


def get_payments_by_user(db_session: Session, user_id: int) -> List[Payment]:
    """Get all payments for a user"""
    return db.get_payments_by_user(user_id)


def update_payment_status(db_session: Session, payment_id: int, status: PaymentStatus) -> Optional[Payment]:
    """Update payment status"""
    return db.update_payment_status(payment_id, status.value)


def update_payment_yativo_details(
    db_session: Session, 
    payment_id: int, 
    yativo_deposit_id: str, 
    yativo_customer_id: Optional[str] = None,
    checkout_url: Optional[str] = None,
    payment_method: Optional[str] = None
) -> Optional[Payment]:
    """Update payment with Yativo details"""
    return db.update_payment_yativo_details(
        payment_id, 
        yativo_deposit_id, 
        yativo_customer_id, 
        checkout_url, 
        payment_method
    )


def get_payment_by_yativo_deposit_id(db_session: Session, yativo_deposit_id: str) -> Optional[Payment]:
    """Get payment by Yativo deposit ID"""
    return db.get_payment_by_yativo_deposit_id(yativo_deposit_id)
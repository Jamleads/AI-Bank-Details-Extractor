"""
SQLAlchemy models for the database
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
import enum

from app.db.database import Base


class SubscriptionTier(enum.Enum):
    """Subscription tier enum"""
    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    google_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, default=datetime.now)
    
    # Subscription information
    subscription_tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    subscription_updated_at = Column(DateTime, default=datetime.now)

    # Relationship with bank records
    bank_records = relationship("BankRecord", back_populates="user")
    # Relationship with header configurations
    header_configs = relationship("HeaderConfig", back_populates="user")
    # Relationship with raw extractions
    raw_extractions = relationship("RawExtraction", back_populates="user")
    # Relationship with payments
    payments = relationship("Payment", back_populates="user")


class BankRecord(Base):
    """Bank record model"""
    __tablename__ = "bank_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    source_pdf = Column(String)
    extraction_date = Column(DateTime, default=datetime.now)
    
    # Bank details
    account_number = Column(String, nullable=True)
    account_name = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    sort_code = Column(String, nullable=True)
    iban = Column(String, nullable=True)
    swift_code = Column(String, nullable=True)
    routing_number = Column(String, nullable=True)
    bsb_code = Column(String, nullable=True)
    branch_code = Column(String, nullable=True)
    branch_address = Column(Text, nullable=True)
    account_type = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    balance = Column(String, nullable=True)
    other_details = Column(Text, nullable=True)

    # Relationship with user
    user = relationship("User", back_populates="bank_records")


class HeaderConfig(Base):
    """Header configuration model for CSV/Excel exports"""
    __tablename__ = "header_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)  # Configuration name (e.g., "Default", "Custom 1")
    is_default = Column(Integer, default=0)  # 1 if this is the user's default config
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # JSON field to store header mappings: {"original_field": "custom_header", ...}
    header_mappings = Column(JSON, nullable=False)
    
    # File format preference (csv or xlsx)
    file_format = Column(String, default="csv")
    
    # Relationship with user
    user = relationship("User", back_populates="header_configs")


class RawExtraction(Base):
    """Model to store raw JSON data from Gemini extractions"""
    __tablename__ = "raw_extractions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    source_pdf = Column(String, nullable=False)
    extraction_date = Column(DateTime, default=datetime.now)
    raw_data = Column(JSON, nullable=True)  # Store the raw JSON response
    
    # Relationship with user
    user = relationship("User", back_populates="raw_extractions") 
"""
SQLAlchemy models for the database
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


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

    # Relationship with bank records
    bank_records = relationship("BankRecord", back_populates="user")


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
"""
Pydantic models for bank details
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class BankDetail(BaseModel):
    """Model for individual bank details"""
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    sort_code: Optional[str] = None
    iban: Optional[str] = None
    swift_code: Optional[str] = None
    routing_number: Optional[str] = None
    bsb_code: Optional[str] = None
    branch_code: Optional[str] = None
    branch_address: Optional[str] = None
    account_type: Optional[str] = None
    currency: Optional[str] = None
    balance: Optional[str] = None
    other_details: Optional[str] = None


class BankDetailResponse(BaseModel):
    """Response model for bank details extraction"""
    bank_details: List[BankDetail] = Field(default_factory=list)


class CSVRecord(BankDetail):
    """Model for CSV record with additional fields"""
    id: Optional[int] = None
    user_id: Optional[int] = None
    source_pdf: str = "Unknown"
    extraction_date: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class FileInfo(BaseModel):
    """File information model"""
    name: str
    size: int = 0


class ProcessResponse(BaseModel):
    """Response model for PDF processing"""
    success: bool
    error: Optional[str] = None
    records_added: int = 0
    results: List[Dict[str, Any]] = Field(default_factory=list)


class SessionStatus(BaseModel):
    """Response model for session status"""
    files: List[FileInfo] = Field(default_factory=list)
    results: List[Dict[str, Any]] = Field(default_factory=list)
    total_records: int = 0 
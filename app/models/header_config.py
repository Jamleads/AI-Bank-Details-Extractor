"""
Models for header configuration
"""
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class HeaderConfigBase(BaseModel):
    """Base model for header configuration"""
    name: str
    header_mappings: Dict[str, str]
    file_format: str = "csv"
    is_default: bool = False


class HeaderConfigCreate(HeaderConfigBase):
    """Model for creating a header configuration"""
    pass


class HeaderConfigUpdate(BaseModel):
    """Model for updating a header configuration"""
    name: Optional[str] = None
    header_mappings: Optional[Dict[str, str]] = None
    file_format: Optional[str] = None
    is_default: Optional[bool] = None


class HeaderConfigResponse(HeaderConfigBase):
    """Response model for a header configuration"""
    id: int
    user_id: int

    class Config:
        """Pydantic config"""
        from_attributes = True


class HeaderConfig(HeaderConfigBase):
    """Model for a header configuration"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config"""
        from_attributes = True


class DefaultHeaders(BaseModel):
    """Model for default headers"""
    headers: Dict[str, str] = Field(
        default={
            "source_pdf": "Source PDF",
            "extraction_date": "Extraction Date",
            "account_number": "Account Number",
            "account_name": "Account Name",
            "bank_name": "Bank Name",
            "sort_code": "Sort Code",
            "iban": "IBAN",
            "swift_code": "SWIFT Code",
            "routing_number": "Routing Number",
            "bsb_code": "BSB Code",
            "branch_code": "Branch Code",
            "branch_address": "Branch Address",
            "account_type": "Account Type",
            "currency": "Currency",
            "balance": "Balance",
            "other_details": "Other Details"
        }
    ) 
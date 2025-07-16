"""
User models for authentication
"""
from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None


class UserCreate(UserBase):
    """User creation model"""
    google_id: str


class UserDB(UserBase):
    """User database model"""
    id: Union[int, str]  # Accept either integer or string ID
    google_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    """User response model"""
    id: Union[int, str]  # Accept either integer or string ID

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token model"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token data model"""
    email: Optional[str] = None
    sub: Optional[str] = None 
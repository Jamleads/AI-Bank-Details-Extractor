"""
Authentication service for Google OAuth
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User
from app.models.user import UserCreate, UserDB, TokenData

# OAuth setup
oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    client_kwargs={
        "scope": "openid email profile",
        "prompt": "select_account",
    },
)

# JWT setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def create_user(user_data: UserCreate, db: AsyncSession) -> User:
    """
    Create a new user in the database
    
    Args:
        user_data: User data
        db: Database session
        
    Returns:
        Created user
    """
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        # Update last login time
        await db.execute(
            update(User)
            .where(User.id == existing_user.id)
            .values(last_login=datetime.now())
        )
        await db.commit()
        return existing_user
    
    # Create new user
    db_user = User(
        email=user_data.email,
        google_id=user_data.google_id,
        name=user_data.name,
        picture=user_data.picture,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    
    Args:
        data: Token data
        expires_delta: Token expiration time
        
    Returns:
        JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """
    Get user from token
    
    Args:
        token: JWT token
        db: Database session
        
    Returns:
        User or None if token is invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        return user
    except JWTError:
        return None


async def get_current_user(
    request: Request = None,
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user from token or cookie
    
    This function can be used in two ways:
    1. With token from Authorization header (API routes)
    2. With token from cookie (template routes)
    
    Args:
        request: FastAPI request (for cookie access)
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        Current user or None if not authenticated
    """
    # First try to get token from Authorization header
    if token:
        user = await get_user_from_token(token, db)
        if user:
            return user
    
    # Then try to get token from cookie if request is provided
    if request:
        token = request.cookies.get("access_token")
        if token:
            user = await get_user_from_token(token, db)
            if user:
                return user
    
    # No valid token found
    return None


async def get_current_user_required(
    request: Request = None,
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current user with required authentication
    
    Args:
        request: FastAPI request (for cookie access)
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If user is not authenticated
    """
    user = await get_current_user(request, token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
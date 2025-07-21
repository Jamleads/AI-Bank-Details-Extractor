"""
Authentication service for Google OAuth
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_async_db
from app.db.models import User
from app.models.user import UserCreate, UserDB, TokenData
from app.db.adapter import db

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

api_key_routes = [
    "/api/session-status",
    "/api/extract",
    "/api/header-config/default-headers",
    "/api/header-config",
    "/api/header-config/",
    "/api/user/presigned-urls",
]

DYNAMIC_ROUTE_PATTERNS = [
    r"^/api/header-config/[^/]+$",
    r"^/api/admin/users/[^/]+/disable$",
    r"^/api/admin/stats$"
]

def is_api_key_route(path: str) -> bool:
    """Check if the path is an API key route"""
    if path in api_key_routes:
        return True

    for pattern in DYNAMIC_ROUTE_PATTERNS:
        if re.match(pattern, path):
            return True

    return False

async def create_user(user_data: UserCreate, db_session: AsyncSession) -> User:
    """
    Create a new user in the database
    
    Args:
        user_data: User data
        db_session: Database session
        
    Returns:
        Created user
    """
    # Check if user already exists
    existing_user = db.get_user_by_email(user_data.email)
    
    if existing_user:
        # Update last login time
        db.update_user(existing_user.id if hasattr(existing_user, 'id') else existing_user['id'], 
                      {"last_login": datetime.now().isoformat()})
        return existing_user
    
    # Create new user
    user_dict = {
        "email": user_data.email,
        "google_id": user_data.google_id,
        "name": user_data.name,
        "picture": user_data.picture,
        "last_login": datetime.now().isoformat()
    }
    return db.create_user(user_dict)


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


async def get_user_from_token(token: str, db_session: AsyncSession) -> Optional[User]:
    """
    Get user from token
    
    Args:
        token: JWT token
        db_session: Database session
        
    Returns:
        User or None if token is invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        
        return db.get_user_by_email(email)
    except JWTError:
        return None


async def get_current_user(
    request: Request = None,
    token: str = Depends(oauth2_scheme), 
    db_session: AsyncSession = Depends(get_async_db)
) -> Optional[User]:
    """
    Get current user from token or cookie
    
    This function can be used in two ways:
    1. With token from Authorization header (API routes)
    2. With token from cookie (template routes)
    
    Args:
        request: FastAPI request (for cookie access)
        token: JWT token from Authorization header
        db_session: Database session
        
    Returns:
        Current user or None if not authenticated
    """
    # First try to get token from Authorization header
    if token:
        user = await get_user_from_token(token, db_session)
        if user:
            return user
    
    # Then try to get token from cookie if request is provided
    if request:
        token = request.cookies.get("access_token")
        if token:
            user = await get_user_from_token(token, db_session)
            if user:
                return user
    
    # No valid token found
    return None


async def get_user_from_api_key(api_key: str) -> Optional[User]:
    """
    Get user from API key
    """
    api_key = db.get_api_key(api_key)
    if api_key and api_key.get("status") == "active":
        user = db.get_user_by_id(api_key.get("user_id"))
        return user
    else:
        return None


async def get_current_user_required(
    request: Request = None,
    token: str = Depends(oauth2_scheme), 
    db_session: AsyncSession = Depends(get_async_db)
) -> User:
    """
    Get current user with required authentication
    
    Args:
        request: FastAPI request (for cookie access)
        token: JWT token from Authorization header
        db_session: Database session
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If user is not authenticated
    """
    print(f"\n\n\n\n\n\nRequest: {request.headers.get("X-API-KEY")} path: {request.url.path}\n\n\n\n\n\n")
    if request.headers.get("X-API-KEY") and is_api_key_route(request.url.path):
        user = await get_user_from_api_key(request.headers.get("X-API-KEY"))
        if user:
            if user.get("status") == "inactive" or getattr(user, "status", None) == "inactive":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been disabled",
                )
            return user

    user = await get_current_user(request, token, db_session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Check if user is inactive
    if user.get("status") == "inactive" or getattr(user, "status", None) == "inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled",
        )
        
    return user
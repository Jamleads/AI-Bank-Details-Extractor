"""
Authentication routes for Google OAuth
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.config import Config

from app.core.config import settings
from app.db.database import get_db
from app.models.user import UserCreate, UserResponse, Token
from app.services.auth_service import (
    oauth, create_user, create_access_token, 
    get_current_user, get_current_user_required
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/login")
async def login(request: Request):
    """
    Login route - redirects to Google OAuth
    """
    # Create redirect URI for callback
    redirect_uri = request.url_for("auth_callback")
    
    # Redirect to Google OAuth
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    OAuth callback route - handles Google OAuth callback
    """
    # Get token from Google
    token = await oauth.google.authorize_access_token(request)
    
    # Get user info from Google
    user_info = token.get("userinfo")
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not fetch user info from Google"
        )
    
    # Create user in database
    user_data = UserCreate(
        email=user_info["email"],
        name=user_info.get("name"),
        picture=user_info.get("picture"),
        google_id=user_info["sub"]
    )
    
    user = await create_user(user_data, db)
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Create response with cookie
    response = RedirectResponse(url="/")
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.PRODUCTION  # Only secure in production
    )
    
    return response


@router.get("/logout")
async def logout():
    """
    Logout route - clears auth cookie
    """
    response = RedirectResponse(url="/login")
    response.delete_cookie(key="access_token")
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(current_user = Depends(get_current_user_required)):
    """
    Get current user information
    """
    return current_user


@router.get("/token")
async def get_token(current_user = Depends(get_current_user_required)):
    """
    Get a new token for API access
    """
    access_token = create_access_token(
        data={"sub": current_user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"} 
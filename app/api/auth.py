"""
Authentication routes for Google OAuth
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.config import Config
import logging
from authlib.integrations.base_client.errors import OAuthError

from app.core.config import settings
from app.db.database import get_async_db
from app.models.user import UserCreate, UserResponse, Token
from app.services.auth_service import (
    oauth, create_user, create_access_token, 
    get_current_user, get_current_user_required
)

router = APIRouter(prefix="/auth", tags=["auth"], include_in_schema=False)
logger = logging.getLogger(__name__)


@router.get("/google/login")
async def login(request: Request):
    """
    Login route - redirects to Google OAuth
    """
    # Create redirect URI for callback
    redirect_uri = request.url_for("auth_callback")
    logger.debug(f"OAuth redirect URI: {redirect_uri}")
    
    # Redirect to Google OAuth
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    OAuth callback route - handles Google OAuth callback
    """
    try:
        # Get token from Google
        token = await oauth.google.authorize_access_token(request)
        
        # Get user info from Google
        user_info = token.get("userinfo")
        
        if not user_info:
            logger.error("Could not fetch user info from Google")
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
        
        # Check if user is inactive/disabled
        user_status = user.get("status") if isinstance(user, dict) else getattr(user, "status", "active")
        if user_status == "inactive":
            logger.warning(f"Disabled user attempted login: {user_data.email}")
            return RedirectResponse(url="/disabled", status_code=status.HTTP_302_FOUND)
        
        # Create access token - handle both object and dictionary access
        user_email = user["email"] if isinstance(user, dict) else user.email
        
        access_token = create_access_token(
            data={"sub": user_email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        # Create response with cookie
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",
            secure=settings.PRODUCTION  # Only secure in production
        )
        
        logger.debug(f"OAuth login successful for user: {user_email}")
        return response
    
    except OAuthError as e:
        logger.error(f"OAuth error: {str(e)}")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    except Exception as e:
        logger.error(f"Unexpected error during OAuth callback: {str(e)}")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


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
    # Handle both object and dictionary access
    user_email = current_user["email"] if isinstance(current_user, dict) else current_user.email
    
    access_token = create_access_token(
        data={"sub": user_email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"} 
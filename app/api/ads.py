"""
Ads API endpoints
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.models.user import UserDB
from app.utils.auth import get_current_user_required
from app.core.admin_config import is_admin_email
from app.services.ads_service import ads_service

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/ads", tags=["ads"])


async def get_admin_user_required(
    current_user: UserDB = Depends(get_current_user_required)
) -> UserDB:
    """
    Check if the current user is an admin
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if they are an admin
    """
    if not current_user.email or not is_admin_email(current_user.email):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/upload")
async def upload_ad(
    image: UploadFile = File(...),
    ad_text: str = Form(...),
    current_user: UserDB = Depends(get_admin_user_required)
):
    """
    Upload an advertisement image with text
    
    Args:
        image: The ad image file
        ad_text: The advertisement text
        current_user: Current admin user
        
    Returns:
        Ad details
    """
    # Validate image file type
    if not image.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    # Upload the ad
    result = await ads_service.upload_ad(image, ad_text)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload advertisement"
        )
    
    return result


@router.get("/latest")
async def get_latest_ad(
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Get the latest advertisement
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Latest ad details with presigned URL
    """
    ad = ads_service.get_latest_ad()
    
    if not ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No advertisements found"
        )
    
    return ad 
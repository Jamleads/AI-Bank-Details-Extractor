"""
Pricing Actions API routes
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_async_db
from app.models.user import UserDB
from app.utils.auth import get_current_user_required, get_user_id, get_user_email
from app.db import pricing_actions as pricing_actions_crud

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/pricing-actions", tags=["pricing-actions"], include_in_schema=False)


class PricingActionCreate(BaseModel):
    """Model for creating a pricing action record"""
    pricing_tier: str
    price: float


@router.post("/track")
async def track_pricing_action(
    action: PricingActionCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """Track a pricing card click"""
    try:
        # Extract user information
        user_id = get_user_id(current_user)
        user_email = get_user_email(current_user) or ""
        user_name = getattr(current_user, 'name', '') or ""
        user_subscription_tier = getattr(current_user, 'subscription_tier', 'FREE') or "FREE"
        
        # Extract request information
        ip_address = request.client.host if request.client else ""
        user_agent = request.headers.get("user-agent", "")
        
        # Create the pricing action record
        pricing_action = await pricing_actions_crud.create_pricing_action(
            db,
            user_id=str(user_id),
            user_email=user_email,
            pricing_tier=action.pricing_tier,
            price=action.price,
            user_name=user_name,
            user_subscription_tier=user_subscription_tier,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Tracked pricing action: user={user_email}, tier={action.pricing_tier}, price={action.price}")
        
        return {
            "success": True,
            "message": "Pricing action tracked successfully",
            "action_id": pricing_action.get("id")
        }
        
    except Exception as e:
        logger.error(f"Error tracking pricing action: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track pricing action: {str(e)}")


@router.get("/user/{user_id}")
async def get_user_pricing_actions(
    user_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """Get pricing actions for a specific user (admin or own data only)"""
    try:
        # Check if user is requesting their own data or is admin
        current_user_id = str(get_user_id(current_user))
        current_user_email = get_user_email(current_user)
        
        from app.core.admin_config import is_admin_email
        is_admin = current_user_email and is_admin_email(current_user_email)
        
        if user_id != current_user_id and not is_admin:
            raise HTTPException(status_code=403, detail="Access denied")
        
        actions = await pricing_actions_crud.get_pricing_actions_by_user(db, user_id)
        return {"pricing_actions": actions}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user pricing actions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get pricing actions: {str(e)}") 
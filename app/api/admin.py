"""
Admin API endpoints
"""
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.db.database import get_async_db
from app.models.user import UserDB
from app.utils.auth import get_current_user_required
from app.core.admin_config import is_admin_email
from app.db.models import User, BankRecord, RawExtraction
from app.db.adapter import db as db_adapter

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)


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


@router.get("/users")
async def get_users(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_admin_user_required)
):
    """
    Get all users with their stats
    
    Args:
        db: Database session
        current_user: Current admin user
        
    Returns:
        List of users with their stats
    """
    try:
        # For DynamoDB, use the adapter
        # This is a simplified version that doesn't include counts
        users = db_adapter._db_provider.get_all_users()
        
        # Format the response
        users_list = []
        for user in users:
            # Get counts for each user
            user_id = user.get("id")
            extractions = db_adapter._db_provider.get_raw_extractions_by_user(user_id)
            
            users_list.append({
                "id": user_id,
                "email": user.get("email"),
                "name": user.get("name"),
                "google_id": user.get("google_id"),
                "subscription_tier": user.get("subscription_tier", "FREE"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
                "extractions_count": len(extractions),
                "status": user.get("status", "active"),
                "is_admin": is_admin_email(user.get("email", "")) if user.get("email") else False
            })
        
        return users_list
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get users: {str(e)}")


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_admin_user_required)
):
    """
    Get system statistics
    
    Args:
        db: Database session
        current_user: Current admin user
        
    Returns:
        System statistics
    """
    try:
        # For DynamoDB, use the adapter
        users = db_adapter._db_provider.get_all_users()
        users_count = len(users)
        
        # This is inefficient but works for small datasets
        bank_records_count = 0
        extractions_count = 0
        for user in users:
            user_id = user.get("id")
            extractions = db_adapter._db_provider.get_raw_extractions_by_user(user_id)
            extractions_count += len(extractions)
    
        return {
            "users_count": users_count,
            "extractions_count": extractions_count
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}") 
    

@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: str,
    current_user: UserDB = Depends(get_admin_user_required)
):
    """Disable a user by setting their status to inactive
    
    Args:
        user_id: User ID to disable
        current_user: Current admin user
        
    Returns:
        Success message
    """
    try:
        print(f"\n\n\n\n\n\nDisabling user {user_id}\n\n\n\n\n\n")
        # Also disable all their API keys
        db_adapter.set_inactive_on_user_id(user_id)
        
        return {"success": True, "message": f"User {user_id} has been disabled"}
    except Exception as e:
        logger.error(f"Error disabling user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to disable user: {str(e)}")
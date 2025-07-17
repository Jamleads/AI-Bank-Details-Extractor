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
router = APIRouter(prefix="/admin", tags=["admin"])


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
        if db_adapter.db_type == "sqlite":
            # For SQLite, use SQLAlchemy
            # Get users with counts
            users_query = select(
                User,
                func.count(BankRecord.id).label('bank_records_count'),
                func.count(RawExtraction.id).label('extractions_count')
            ).outerjoin(
                BankRecord, User.id == BankRecord.user_id
            ).outerjoin(
                RawExtraction, User.id == RawExtraction.user_id
            ).group_by(User.id)
            
            result = await db.execute(users_query)
            users_with_counts = result.all()
            
            # Format the response
            users_list = []
            for user, bank_records_count, extractions_count in users_with_counts:
                users_list.append({
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "google_id": user.google_id,
                    "subscription_tier": str(user.subscription_tier),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "bank_records_count": bank_records_count,
                    "extractions_count": extractions_count,
                    "is_admin": is_admin_email(user.email) if user.email else False
                })
            
            return users_list
        else:
            # For DynamoDB, use the adapter
            # This is a simplified version that doesn't include counts
            users = db_adapter._db_provider.get_all_users()
            
            # Format the response
            users_list = []
            for user in users:
                # Get counts for each user
                user_id = user.get("id")
                bank_records = db_adapter._db_provider.get_bank_records_by_user(user_id)
                extractions = db_adapter._db_provider.get_raw_extractions_by_user(user_id)
                
                users_list.append({
                    "id": user_id,
                    "email": user.get("email"),
                    "name": user.get("name"),
                    "google_id": user.get("google_id"),
                    "subscription_tier": user.get("subscription_tier", "FREE"),
                    "created_at": user.get("created_at"),
                    "last_login": user.get("last_login"),
                    "bank_records_count": len(bank_records),
                    "extractions_count": len(extractions),
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
        if db_adapter.db_type == "sqlite":
            # For SQLite, use SQLAlchemy
            users_count_query = select(func.count(User.id))
            bank_records_count_query = select(func.count(BankRecord.id))
            extractions_count_query = select(func.count(RawExtraction.id))
            
            users_count_result = await db.execute(users_count_query)
            bank_records_count_result = await db.execute(bank_records_count_query)
            extractions_count_result = await db.execute(extractions_count_query)
            
            users_count = users_count_result.scalar() or 0
            bank_records_count = bank_records_count_result.scalar() or 0
            extractions_count = extractions_count_result.scalar() or 0
        else:
            # For DynamoDB, use the adapter
            users = db_adapter._db_provider.get_all_users()
            users_count = len(users)
            
            # This is inefficient but works for small datasets
            bank_records_count = 0
            extractions_count = 0
            for user in users:
                user_id = user.get("id")
                bank_records = db_adapter._db_provider.get_bank_records_by_user(user_id)
                extractions = db_adapter._db_provider.get_raw_extractions_by_user(user_id)
                bank_records_count += len(bank_records)
                extractions_count += len(extractions)
        
        return {
            "users_count": users_count,
            "bank_records_count": bank_records_count,
            "extractions_count": extractions_count
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}") 
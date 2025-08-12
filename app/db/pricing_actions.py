"""
Pricing Actions database operations
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.adapter import db


async def create_pricing_action(
    db_session: AsyncSession, 
    user_id: str,
    user_email: str, 
    pricing_tier: str,
    price: float,
    user_name: str = "",
    user_subscription_tier: str = "FREE",
    ip_address: str = "",
    user_agent: str = ""
) -> Dict[str, Any]:
    """Create a new pricing action record"""
    action_data = {
        'user_id': user_id,
        'user_email': user_email,
        'pricing_tier': pricing_tier,
        'price': price,
        'user_name': user_name,
        'user_subscription_tier': user_subscription_tier,
        'ip_address': ip_address,
        'user_agent': user_agent
    }
    return db.create_pricing_action(action_data)


async def get_pricing_actions_by_user(db_session: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
    """Get all pricing actions for a user"""
    return db.get_pricing_actions_by_user(user_id)


async def get_all_pricing_actions(db_session: AsyncSession, limit: int = 100) -> List[Dict[str, Any]]:
    """Get all pricing actions across all users"""
    return db.get_all_pricing_actions(limit)


async def get_pricing_actions_stats(db_session: AsyncSession) -> Dict[str, Any]:
    """Get pricing actions statistics"""
    return db.get_pricing_actions_stats() 
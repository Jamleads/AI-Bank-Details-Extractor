"""
Header configuration API routes
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_db
from app.models.user import UserDB
from app.models.header_config import HeaderConfigCreate, HeaderConfigUpdate, HeaderConfigResponse, DefaultHeaders
from app.utils.auth import get_current_user_required, get_user_id
from app.db.header_config import create_header_config, get_header_configs, ensure_default_config, get_header_config, update_header_config, delete_header_config

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/api/header-config")


@router.get("/default-headers")
async def get_default_headers():
    """
    Get the default headers
    
    Returns:
        Default headers
    """
    return DefaultHeaders()


@router.post("/", response_model=HeaderConfigResponse)
async def create_config(
    config: HeaderConfigCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Create a new header configuration
    
    Args:
        config: Header configuration data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Created header configuration
    """
    try:
        return await create_header_config(config, get_user_id(current_user), db)
    except Exception as e:
        logger.error(f"Error creating header config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[HeaderConfigResponse])
async def get_configs(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Get all header configurations for the current user
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of header configurations
    """
    try:
        return await get_header_configs(get_user_id(current_user), db)
    except Exception as e:
        logger.error(f"Error getting header configs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/default", response_model=HeaderConfigResponse)
async def get_default_config(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Get the default header configuration for the current user
    If none exists, create one with system defaults
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Default header configuration
    """
    try:
        return await ensure_default_config(get_user_id(current_user), db)
    except Exception as e:
        logger.error(f"Error getting default header config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}", response_model=HeaderConfigResponse)
async def get_config(
    config_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Get a header configuration by ID
    
    Args:
        config_id: Header configuration ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Header configuration
    """
    try:
        config = await get_header_config(config_id, get_user_id(current_user), db)
        if not config:
            raise HTTPException(status_code=404, detail="Header configuration not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting header config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}", response_model=HeaderConfigResponse)
async def update_config(
    config_id: int,
    config_update: HeaderConfigUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Update a header configuration
    
    Args:
        config_id: Header configuration ID
        config_update: Header configuration update
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated header configuration
    """
    try:
        config = await update_header_config(config_id, config_update, get_user_id(current_user), db)
        if not config:
            raise HTTPException(status_code=404, detail="Header configuration not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating header config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}")
async def delete_config(
    config_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Delete a header configuration
    
    Args:
        config_id: Header configuration ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    try:
        success = await delete_header_config(config_id, get_user_id(current_user), db)
        if not success:
            raise HTTPException(status_code=404, detail="Header configuration not found")
        return {"success": True, "message": "Header configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting header config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
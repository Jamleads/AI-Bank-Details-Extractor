"""
Header configuration API routes
"""
import logging
from typing import List, Dict, Any, Optional, Union
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
router = APIRouter(prefix="/api/header-config", tags=["header-config"])


@router.get("/default-headers", response_model=DefaultHeaders, description="Get the default headers")
async def get_default_headers():
    """
    Get the default headers
    
    Returns:
        Default headers
    """
    return DefaultHeaders()


@router.post("/", response_model=HeaderConfigResponse, description="Create a new header configuration")
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
        return await create_header_config(get_user_id(current_user), config.dict())
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


@router.get("/{config_id}", response_model=HeaderConfigResponse, description="Get a header configuration by ID")
async def get_header_config_by_id(
    config_id: Union[int, str],
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


@router.put("/{config_id}", response_model=HeaderConfigResponse, include_in_schema=False)
async def update_config(
    config_id: Union[int, str],
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
        # Convert to dict for compatibility with both SQLite and DynamoDB
        update_data = config_update.dict(exclude_unset=True)
        
        # Get the user ID
        user_id = get_user_id(current_user)
        
        # Check if this is setting a new default
        if update_data.get('is_default'):
            # Get all user configs
            configs = await get_header_configs(user_id, db)
            # Unset default on other configs if this one is being set as default
            for config in configs:
                # Handle both object and dictionary access
                config_id_value = config.get('id', getattr(config, 'id', None)) if isinstance(config, dict) else config.id
                is_default = config.get('is_default', getattr(config, 'is_default', False)) if isinstance(config, dict) else config.is_default
                
                if config_id_value != config_id and is_default:
                    await update_header_config(config_id_value, {"is_default": False}, db)
        
        # Update the config
        config = await update_header_config(config_id, update_data, db)
        if not config:
            raise HTTPException(status_code=404, detail="Header configuration not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating header config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}", include_in_schema=False)
async def delete_config(
    config_id: Union[int, str],
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
        # Get user ID
        user_id = get_user_id(current_user)
        
        # Check if config exists and belongs to user
        config = await get_header_config(config_id, user_id, db)
        if not config:
            raise HTTPException(status_code=404, detail="Header configuration not found")
        
        # Check if it's the default config - handle both object and dictionary
        is_default = config.get('is_default', False) if isinstance(config, dict) else getattr(config, 'is_default', False)
        if is_default:
            raise HTTPException(status_code=400, detail="Cannot delete the default configuration")
        
        # Delete the config
        success = await delete_header_config(config_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="Header configuration not found")
        
        return {"success": True, "message": "Header configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting header config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
"""
Service for managing header configurations
"""
import logging
from typing import Dict, List, Optional, Union

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HeaderConfig, User
from app.models.header_config import HeaderConfigCreate, HeaderConfigUpdate, DefaultHeaders

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def create_header_config(
    config: HeaderConfigCreate,
    user_id: int,
    db: AsyncSession
) -> HeaderConfig:
    """
    Create a new header configuration
    
    Args:
        config: Header configuration to create
        user_id: User ID
        db: Database session
        
    Returns:
        Created header configuration
    """
    try:
        # If this is set as default, unset any existing defaults
        if config.is_default:
            await db.execute(
                update(HeaderConfig)
                .where(HeaderConfig.user_id == user_id)
                .values(is_default=0)
            )
            
        # Create new config
        db_config = HeaderConfig(
            user_id=user_id,
            name=config.name,
            header_mappings=config.header_mappings,
            file_format=config.file_format,
            is_default=1 if config.is_default else 0
        )
        
        db.add(db_config)
        await db.commit()
        await db.refresh(db_config)
        
        logger.debug(f"Created header config {db_config.id} for user {user_id}")
        return db_config
    except Exception as e:
        logger.error(f"Error creating header config: {str(e)}")
        await db.rollback()
        raise


async def get_header_configs(
    user_id: int,
    db: AsyncSession
) -> List[HeaderConfig]:
    """
    Get all header configurations for a user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        List of header configurations
    """
    try:
        result = await db.execute(
            select(HeaderConfig)
            .where(HeaderConfig.user_id == user_id)
        )
        
        configs = result.scalars().all()
        logger.debug(f"Found {len(configs)} header configs for user {user_id}")
        return configs
    except Exception as e:
        logger.error(f"Error getting header configs: {str(e)}")
        raise


async def get_header_config(
    config_id: int,
    user_id: int,
    db: AsyncSession
) -> Optional[HeaderConfig]:
    """
    Get a header configuration by ID
    
    Args:
        config_id: Header configuration ID
        user_id: User ID
        db: Database session
        
    Returns:
        Header configuration or None if not found
    """
    try:
        result = await db.execute(
            select(HeaderConfig)
            .where(
                HeaderConfig.id == config_id,
                HeaderConfig.user_id == user_id
            )
        )
        
        config = result.scalars().first()
        if config:
            logger.debug(f"Found header config {config_id} for user {user_id}")
        else:
            logger.debug(f"Header config {config_id} not found for user {user_id}")
        return config
    except Exception as e:
        logger.error(f"Error getting header config: {str(e)}")
        raise


async def get_default_header_config(
    user_id: int,
    db: AsyncSession
) -> Optional[HeaderConfig]:
    """
    Get the default header configuration for a user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        Default header configuration or None if not found
    """
    try:
        result = await db.execute(
            select(HeaderConfig)
            .where(
                HeaderConfig.user_id == user_id,
                HeaderConfig.is_default == 1
            )
        )
        
        config = result.scalars().first()
        if config:
            logger.debug(f"Found default header config {config.id} for user {user_id}")
        else:
            logger.debug(f"No default header config found for user {user_id}")
        return config
    except Exception as e:
        logger.error(f"Error getting default header config: {str(e)}")
        raise


async def update_header_config(
    config_id: int,
    config_update: HeaderConfigUpdate,
    user_id: int,
    db: AsyncSession
) -> Optional[HeaderConfig]:
    """
    Update a header configuration
    
    Args:
        config_id: Header configuration ID
        config_update: Header configuration update
        user_id: User ID
        db: Database session
        
    Returns:
        Updated header configuration or None if not found
    """
    try:
        # Check if config exists and belongs to user
        existing_config = await get_header_config(config_id, user_id, db)
        if not existing_config:
            return None
            
        # Prepare update values
        update_values = {}
        if config_update.name is not None:
            update_values["name"] = config_update.name
        if config_update.header_mappings is not None:
            update_values["header_mappings"] = config_update.header_mappings
        if config_update.file_format is not None:
            update_values["file_format"] = config_update.file_format
        if config_update.is_default is not None:
            update_values["is_default"] = 1 if config_update.is_default else 0
            
            # If setting as default, unset any existing defaults
            if config_update.is_default:
                await db.execute(
                    update(HeaderConfig)
                    .where(
                        HeaderConfig.user_id == user_id,
                        HeaderConfig.id != config_id
                    )
                    .values(is_default=0)
                )
        
        # Update config if there are changes
        if update_values:
            await db.execute(
                update(HeaderConfig)
                .where(
                    HeaderConfig.id == config_id,
                    HeaderConfig.user_id == user_id
                )
                .values(**update_values)
            )
            
            await db.commit()
            
            # Refresh config
            result = await db.execute(
                select(HeaderConfig)
                .where(HeaderConfig.id == config_id)
            )
            
            updated_config = result.scalars().first()
            logger.debug(f"Updated header config {config_id} for user {user_id}")
            return updated_config
        
        return existing_config
    except Exception as e:
        logger.error(f"Error updating header config: {str(e)}")
        await db.rollback()
        raise


async def delete_header_config(
    config_id: int,
    user_id: int,
    db: AsyncSession
) -> bool:
    """
    Delete a header configuration
    
    Args:
        config_id: Header configuration ID
        user_id: User ID
        db: Database session
        
    Returns:
        True if deleted, False if not found
    """
    try:
        # Check if config exists and belongs to user
        existing_config = await get_header_config(config_id, user_id, db)
        if not existing_config:
            return False
            
        # Delete config
        await db.execute(
            delete(HeaderConfig)
            .where(
                HeaderConfig.id == config_id,
                HeaderConfig.user_id == user_id
            )
        )
        
        await db.commit()
        logger.debug(f"Deleted header config {config_id} for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting header config: {str(e)}")
        await db.rollback()
        raise


async def ensure_default_config(
    user_id: int,
    db: AsyncSession
) -> HeaderConfig:
    """
    Ensure the user has a default header configuration
    If not, create one with system defaults
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        Default header configuration
    """
    try:
        # Check if user has a default config
        default_config = await get_default_header_config(user_id, db)
        if default_config:
            return default_config
            
        # Create default config
        default_headers = DefaultHeaders().headers
        config = HeaderConfigCreate(
            name="Default",
            header_mappings=default_headers,
            file_format="csv",
            is_default=True
        )
        
        return await create_header_config(config, user_id, db)
    except Exception as e:
        logger.error(f"Error ensuring default config: {str(e)}")
        raise


def apply_header_mapping(
    records: List[Dict],
    header_mapping: Dict[str, str]
) -> List[Dict]:
    """
    Apply header mapping to records
    
    Args:
        records: List of records
        header_mapping: Header mapping
        
    Returns:
        List of records with mapped headers
    """
    mapped_records = []
    
    for record in records:
        mapped_record = {}
        for field, value in record.items():
            # Use mapped header if available, otherwise use original
            if header_mapping.get(field, None):
                mapped_record[header_mapping.get(field, None)] = value
        mapped_records.append(mapped_record)
        
    return mapped_records 
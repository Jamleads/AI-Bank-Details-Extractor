"""
Header configuration operations
"""
from typing import Dict, List, Any, Union, Optional
from app.db.adapter import DatabaseAdapter

# Initialize database adapter
db_adapter = DatabaseAdapter()

async def create_header_config(user_id: Union[int, str], config_data: Dict[str, Any]):
    """
    Create a new header configuration
    
    Args:
        user_id: User ID
        config_data: Header configuration data
        
    Returns:
        Created header configuration
    """
    # Add user_id to config data
    config_data["user_id"] = user_id
    return db_adapter.create_header_config(config_data)

async def get_header_configs(user_id: Union[int, str], db = None):
    """
    Get all header configurations for a user
    
    Args:
        user_id: User ID
        db: Database session (optional, for compatibility)
        
    Returns:
        List of header configurations
    """
    return db_adapter.get_header_configs_by_user(user_id)

async def get_header_config(config_id: Union[int, str], user_id: Union[int, str] = None, db = None):
    """
    Get header configuration by ID
    
    Args:
        config_id: Configuration ID
        user_id: User ID (optional, for permission checking)
        db: Database session (optional, for compatibility)
        
    Returns:
        Header configuration
    """
    return db_adapter.get_header_config(config_id)

async def update_header_config(config_id: Union[int, str], config_data: Dict[str, Any], db = None):
    """
    Update header configuration
    
    Args:
        config_id: Configuration ID
        config_data: Header configuration data
        db: Database session (optional, for compatibility)
        
    Returns:
        Updated header configuration
    """
    return db_adapter.update_header_config(config_id, config_data)

async def delete_header_config(config_id: Union[int, str], db = None):
    """
    Delete header configuration
    
    Args:
        config_id: Configuration ID
        db: Database session (optional, for compatibility)
        
    Returns:
        Number of records deleted
    """
    return db_adapter.delete_header_config(config_id)

async def ensure_default_config(user_id: Union[int, str], db = None):
    """
    Ensure user has a default header configuration
    
    Args:
        user_id: User ID
        db: Database session (optional, for compatibility)
        
    Returns:
        Default header configuration
    """
    configs = await get_header_configs(user_id, db)
    
    # Check if there's a default config
    default_config = None
    for config in configs:
        if hasattr(config, 'is_default') and config.is_default:
            default_config = config
            break
        elif isinstance(config, dict) and config.get('is_default'):
            default_config = config
            break
    
    # If no default config, create one
    if not default_config:
        default_mappings = {
            "account_number": "Account Number",
            "account_name": "Account Name",
            "bank_name": "Bank Name",
            "sort_code": "Sort Code",
            "iban": "IBAN",
            "swift_code": "SWIFT/BIC",
            "routing_number": "Routing Number",
            "bsb_code": "BSB Code",
            "branch_code": "Branch Code",
            "branch_address": "Branch Address",
            "account_type": "Account Type",
            "currency": "Currency",
            "balance": "Balance",
            "other_details": "Other Details"
        }
        
        config_data = {
            "name": "Default",
            "is_default": True,
            "header_mappings": default_mappings,
            "file_format": "csv"
        }
        
        default_config = await create_header_config(user_id, config_data)
    
    return default_config 
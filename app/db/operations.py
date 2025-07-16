"""
Database operations for bank details
"""
from typing import Dict, List, Any, Union
from app.db.adapter import DatabaseAdapter

# Initialize database adapter
db_adapter = DatabaseAdapter()

async def save_bank_details(user_id: Union[int, str], bank_details: List[Any]):
    """
    Save bank details to database
    
    Args:
        user_id: User ID
        bank_details: List of bank detail records (can be dicts or BankDetail objects)
        
    Returns:
        Dictionary with number of records added
    """
    records_added = 0
    for detail in bank_details:
        # Convert BankDetail object to dict if needed
        if hasattr(detail, 'model_dump'):
            # For Pydantic v2
            detail_dict = detail.model_dump()
        elif hasattr(detail, 'dict'):
            # For older Pydantic versions
            detail_dict = detail.dict()
        else:
            # Already a dict
            detail_dict = detail
            
        # Add user_id to the dict
        detail_dict["user_id"] = user_id
        
        # Ensure source_pdf exists
        if "source_pdf" not in detail_dict or not detail_dict["source_pdf"]:
            detail_dict["source_pdf"] = "Unknown"
        
        # Create the record
        db_adapter.create_bank_record(detail_dict)
        records_added += 1
        
    return {"records_added": records_added, "success": True}

async def get_user_records(user_id: Union[int, str], db = None):
    """
    Get all bank records for a user
    
    Args:
        user_id: User ID
        db: Database session (optional, for compatibility)
        
    Returns:
        List of bank records
    """
    records = db_adapter.get_bank_records_by_user(user_id)
    return records

async def get_processed_files(user_id: Union[int, str], db = None):
    """
    Get all processed files for a user
    
    Args:
        user_id: User ID
        db: Database session (optional, for compatibility)
        
    Returns:
        List of processed files
    """
    records = db_adapter.get_bank_records_by_user(user_id)
    # Extract unique source_pdf values
    files = set()
    for record in records:
        if hasattr(record, 'source_pdf'):
            files.add(record.source_pdf)
        elif isinstance(record, dict) and 'source_pdf' in record:
            files.add(record['source_pdf'])
    return list(files)

async def count_user_records(user_id: Union[int, str], db = None):
    """
    Count bank records for a user
    
    Args:
        user_id: User ID
        db: Database session (optional, for compatibility)
        
    Returns:
        Number of records
    """
    records = db_adapter.get_bank_records_by_user(user_id)
    return len(records)

async def save_raw_extraction(user_id: Union[int, str], filename: str, extraction_data: Dict[str, Any], db = None):
    """
    Save raw extraction data
    
    Args:
        user_id: User ID
        filename: Source filename
        extraction_data: Raw extraction data
        db: Database session (optional, for compatibility)
        
    Returns:
        Dictionary with success status and created extraction record
    """
    try:
        data = {
            "user_id": user_id,
            "source_pdf": filename,
            "raw_json": extraction_data
        }
        result = db_adapter.create_raw_extraction(data)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_raw_extractions(user_id: Union[int, str], db = None):
    """
    Get raw extractions for a user
    
    Args:
        user_id: User ID
        db: Database session (optional, for compatibility)
        
    Returns:
        List of raw extractions
    """
    return db_adapter.get_raw_extractions_by_user(user_id)

async def clear_user_session(user_id: Union[int, str], db = None):
    """
    Clear user session data (delete all raw extractions)
    
    Args:
        user_id: User ID
        db: Database session (optional, for compatibility)
        
    Returns:
        Number of records deleted
    """
    return db_adapter.delete_raw_extractions_by_user(user_id) 
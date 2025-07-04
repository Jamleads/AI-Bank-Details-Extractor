"""
Service for bank record database operations
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.db.models import BankRecord, User
from app.models.bank_details import BankDetail, CSVRecord


async def save_bank_details(
    bank_details: List[BankDetail], 
    source_pdf: str, 
    user_id: int,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Save bank details to database
    
    Args:
        bank_details: List of bank details to save
        source_pdf: Source PDF filename
        user_id: User ID
        db: Database session
        
    Returns:
        Dictionary with operation results
    """
    if not bank_details:
        return {
            'success': False,
            'error': "No bank details found in the response",
            'records_added': 0,
            'total_records': 0
        }
    
    try:
        records_added = 0
        
        # Add records to database
        for record in bank_details:
            db_record = BankRecord(
                user_id=user_id,
                source_pdf=source_pdf or 'Unknown',
                extraction_date=datetime.now(),
                account_number=record.account_number,
                account_name=record.account_name,
                bank_name=record.bank_name,
                sort_code=record.sort_code,
                iban=record.iban,
                swift_code=record.swift_code,
                routing_number=record.routing_number,
                bsb_code=record.bsb_code,
                branch_code=record.branch_code,
                branch_address=record.branch_address,
                account_type=record.account_type,
                currency=record.currency,
                balance=record.balance,
                other_details=record.other_details
            )
            db.add(db_record)
            records_added += 1
        
        # Commit changes
        await db.commit()
        
        # Get total records for user
        total_records = await count_user_records(user_id, db)
        
        return {
            'success': True,
            'records_added': records_added,
            'total_records': total_records,
            'message': f"Added {records_added} records to database"
        }
        
    except Exception as e:
        await db.rollback()
        return {
            'success': False,
            'error': f"Error saving to database: {str(e)}",
            'records_added': 0,
            'total_records': 0
        }


async def get_user_records(user_id: int, db: AsyncSession) -> List[CSVRecord]:
    """
    Get all bank records for a user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        List of bank records
    """
    result = await db.execute(
        select(BankRecord).where(BankRecord.user_id == user_id)
    )
    records = result.scalars().all()
    
    # Convert to Pydantic models
    return [
        CSVRecord(
            id=record.id,
            user_id=record.user_id,
            source_pdf=record.source_pdf,
            extraction_date=record.extraction_date,
            account_number=record.account_number,
            account_name=record.account_name,
            bank_name=record.bank_name,
            sort_code=record.sort_code,
            iban=record.iban,
            swift_code=record.swift_code,
            routing_number=record.routing_number,
            bsb_code=record.bsb_code,
            branch_code=record.branch_code,
            branch_address=record.branch_address,
            account_type=record.account_type,
            currency=record.currency,
            balance=record.balance,
            other_details=record.other_details
        )
        for record in records
    ]


async def get_processed_files(user_id: int, db: AsyncSession) -> List[str]:
    """
    Get list of unique PDF files that have been processed for a user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        List of unique PDF filenames
    """
    result = await db.execute(
        select(BankRecord.source_pdf)
        .where(BankRecord.user_id == user_id)
        .distinct()
    )
    
    files = result.scalars().all()
    return sorted([file for file in files if file and file != 'Unknown'])


async def count_user_records(user_id: int, db: AsyncSession) -> int:
    """
    Count total number of records for a user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        Total number of records
    """
    result = await db.execute(
        select(BankRecord)
        .where(BankRecord.user_id == user_id)
    )
    
    records = result.scalars().all()
    return len(records)


async def clear_user_session(user_id: int, db: AsyncSession) -> bool:
    """
    Clear all records for a user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        Success status
    """
    try:
        await db.execute(
            delete(BankRecord)
            .where(BankRecord.user_id == user_id)
        )
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        return False 
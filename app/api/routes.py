"""
API routes for the application
"""
import os
import csv
import tempfile
import traceback
import logging
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response, Request, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.utils import secure_filename

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User
from app.models.bank_details import ProcessResponse, SessionStatus
from app.models.user import UserResponse
from app.services.gemini_service import GeminiService
from app.services.bank_record_service import (
    save_bank_details, 
    get_user_records, 
    get_processed_files,
    count_user_records,
    clear_user_session
)
from app.services.auth_service import get_current_user_required

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/api")

# Templates
templates = Jinja2Templates(directory="app/templates")


# Dependencies
def get_gemini_service():
    """Dependency for Gemini service"""
    return GeminiService()


@router.get("/")
async def index(request: Request):
    """Main page"""
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/extract", response_model=ProcessResponse)
async def extract_bank_details(
    files: List[UploadFile] = File(...),
    gemini_service: GeminiService = Depends(get_gemini_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Process uploaded PDF files and extract bank details
    
    Args:
        files: Uploaded PDF files
        gemini_service: Gemini AI service
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        ProcessResponse with operation results
    """
    try:
        logger.debug(f"Extract endpoint called with {len(files)} files")
        
        if not files:
            logger.warning("No files provided")
            raise HTTPException(status_code=400, detail="No files selected")
        
        total_records_added = 0
        all_results = []
        
        for pdf_file in files:
            # Validate file
            if not pdf_file.filename:
                logger.warning("File has no filename")
                continue
                
            if not pdf_file.filename.lower().endswith('.pdf'):
                logger.warning(f"File {pdf_file.filename} is not a PDF")
                continue
                
            # Secure the filename
            filename = secure_filename(pdf_file.filename)
            logger.debug(f"Processing file: {filename}")
            
            try:
                # Read file content
                file_content = await pdf_file.read()
                logger.debug(f"File {filename} read successfully, size: {len(file_content)} bytes")
                
                # Extract bank details with Gemini
                logger.debug(f"Calling Gemini API for file {filename}")
                bank_details = gemini_service.extract_bank_details(file_content)
                logger.debug(f"Gemini API returned {len(bank_details)} records for file {filename}")
                
                # Save to database
                logger.debug(f"Saving {len(bank_details)} records to database for file {filename}")
                result = await save_bank_details(bank_details, filename, current_user.id, db)
                total_records_added += result.get('records_added', 0)
                logger.debug(f"Added {result.get('records_added', 0)} records to database for file {filename}")
                
                # Add results to response
                for record in bank_details:
                    # Convert Pydantic model to dict and add source_pdf
                    record_dict = record.dict()
                    record_dict["source_pdf"] = filename
                    all_results.append(record_dict)
            except Exception as e:
                logger.error(f"Error processing file {filename}: {str(e)}")
                logger.error(traceback.format_exc())
                continue
        
        logger.debug(f"Extract endpoint completed successfully with {total_records_added} total records added")
        # Return response
        return ProcessResponse(
            success=True,
            records_added=total_records_added,
            results=all_results
        )
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        logger.error(f"HTTP Exception in extract endpoint: {str(he)}")
        raise
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Unhandled exception in extract endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session-status", response_model=SessionStatus)
async def get_session_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Get the current session status
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        SessionStatus with current session information
    """
    try:
        # Get processed files
        processed_files = await get_processed_files(current_user.id, db)
        
        # Get total records
        total_records = await count_user_records(current_user.id, db)
        
        # Get all records
        records = await get_user_records(current_user.id, db)
        
        # Convert records to dict for response
        results = []
        for record in records:
            results.append({
                'source_pdf': record.source_pdf,
                'account_number': record.account_number,
                'account_name': record.account_name,
                'bank_name': record.bank_name,
                'sort_code': record.sort_code,
                'iban': record.iban,
                'swift_code': record.swift_code,
                'routing_number': record.routing_number,
                'bsb_code': record.bsb_code,
                'branch_code': record.branch_code,
                'branch_address': record.branch_address,
                'account_type': record.account_type,
                'currency': record.currency,
                'balance': record.balance,
                'other_details': record.other_details
            })
        
        # Create file info list
        files = []
        for filename in processed_files:
            files.append({
                "name": filename,
                "size": 0  # Size not available from DB
            })
        
        return SessionStatus(
            files=files,
            results=results,
            total_records=total_records
        )
    except Exception as e:
        logger.error(f"Error in session-status endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-session")
async def clear_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Clear the current session
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    try:
        success = await clear_user_session(current_user.id, db)
        if success:
            return {"success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear session")
    except Exception as e:
        logger.error(f"Error in clear-session endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Function to remove temporary file
def remove_temp_file(file_path: str):
    """Remove temporary file after response is sent"""
    try:
        os.unlink(file_path)
        logger.debug(f"Temporary file {file_path} removed")
    except Exception as e:
        logger.error(f"Error removing temporary file {file_path}: {str(e)}")


@router.get("/download-csv")
async def download_csv(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Download the CSV file with user's bank details
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with CSV file
    """
    try:
        logger.debug("Download CSV endpoint called")
        # Get user records
        records = await get_user_records(current_user.id, db)
        
        if not records:
            logger.warning("No records found for download")
            raise HTTPException(
                status_code=400, 
                detail="No records found. Please process some PDFs first."
            )
        
        logger.debug(f"Found {len(records)} records for download")
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as temp_file:
            # Define CSV headers
            headers = [
                'source_pdf',
                'extraction_date',
                'account_number',
                'account_name',
                'bank_name',
                'sort_code',
                'iban',
                'swift_code',
                'routing_number',
                'bsb_code',
                'branch_code',
                'branch_address',
                'account_type',
                'currency',
                'balance',
                'other_details'
            ]
            
            # Write CSV
            writer = csv.DictWriter(temp_file, fieldnames=headers)
            writer.writeheader()
            
            for record in records:
                writer.writerow({
                    'source_pdf': record.source_pdf,
                    'extraction_date': record.extraction_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'account_number': record.account_number,
                    'account_name': record.account_name,
                    'bank_name': record.bank_name,
                    'sort_code': record.sort_code,
                    'iban': record.iban,
                    'swift_code': record.swift_code,
                    'routing_number': record.routing_number,
                    'bsb_code': record.bsb_code,
                    'branch_code': record.branch_code,
                    'branch_address': record.branch_address,
                    'account_type': record.account_type,
                    'currency': record.currency,
                    'balance': record.balance,
                    'other_details': record.other_details
                })
        
            logger.debug(f"CSV file created at {temp_file.name}")
            file_path = temp_file.name
        
        # Add task to remove the file after the response is sent
        background_tasks.add_task(remove_temp_file, file_path)
        
        # Return the CSV file
        return FileResponse(
            path=file_path,
            media_type='text/csv',
            filename='bank_details.csv'
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error in download-csv endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check_file/{filename}")
async def check_file(
    filename: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if a user has records
    
    Args:
        filename: Filename to check
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Status of file existence
    """
    try:
        if not filename.endswith('.csv'):
            return {"exists": False, "error": "Invalid file format"}
            
        # Check if user has records
        total_records = await count_user_records(current_user.id, db)
        return {"exists": total_records > 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
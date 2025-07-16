"""
API routes for bank details extraction
"""
import os
import io
import zipfile
import traceback
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.utils import secure_filename
from app.db.database import get_async_db
from app.models.user import UserDB
from app.models.bank_details import BankDetail
from app.models.response import ProcessResponse, SessionStatus
from app.services.gemini_service import GeminiService
from app.utils.auth import get_current_user_required, get_user_id
from app.utils.file import generate_csv_file, generate_json_file, generate_excel_file
from app.services.header_config_service import apply_header_mapping
from app.db.operations import (
    save_bank_details, 
    get_user_records, 
    get_processed_files,
    count_user_records,
    save_raw_extraction,
    get_raw_extractions,
    clear_user_session
)
from app.db.header_config import get_header_config, ensure_default_config
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/api")

# Include payment router
# router.include_router(payment_router, prefix="/payment", tags=["payment"]) # This line was removed as per the new_code, as payment_router is no longer imported.

# Templates
# templates = Jinja2Templates(directory="app/templates") # This line was removed as per the new_code, as templates are no longer used.


# Dependencies
def get_gemini_service():
    """Dependency for Gemini service"""
    return GeminiService()


@router.get("/")
async def index(request: Request):
    """Main page"""
    # return templates.TemplateResponse("index.html", {"request": request}) # This line was removed as per the new_code, as templates are no longer used.
    return {"message": "Welcome to the Bank Details Extraction API"}


async def extract_zip_files(zip_data: bytes) -> List[Dict[str, Any]]:
    """
    Extract files from a ZIP archive
    
    Args:
        zip_data: Raw ZIP file data
        
    Returns:
        List of dictionaries with extracted file data:
            {
                'filename': str,
                'data': bytes,
                'ext': str
            }
    """
    extracted_files = []
    
    try:
        # Check if data is empty
        if not zip_data or len(zip_data) < 100:  # Minimum size for a valid ZIP
            logger.warning("ZIP data is empty or too small")
            return []
        
        # Try to open the ZIP
        zip_file = io.BytesIO(zip_data)
        
        with zipfile.ZipFile(zip_file) as zf:
            # Check if ZIP has files
            if len(zf.namelist()) == 0:
                logger.warning("ZIP file is empty")
                return []
            
            # Extract supported files
            for file_info in zf.infolist():
                # Skip directories and hidden files
                if file_info.filename.endswith('/') or file_info.filename.startswith('__MACOSX') or file_info.filename.startswith('.'):
                    continue
                
                # Get file extension
                file_ext = '.' + file_info.filename.split('.')[-1].lower() if '.' in file_info.filename else ''
                
                # Only extract supported files
                if file_ext in ['.pdf', '.png', '.jpg', '.jpeg', '.webp']:
                    try:
                        # Extract file data
                        file_data = zf.read(file_info.filename)
                        
                        # Only add if file has content
                        if file_data and len(file_data) > 100:
                            extracted_files.append({
                                'filename': file_info.filename,
                                'data': file_data,
                                'ext': file_ext
                            })
                    except Exception as e:
                        logger.warning(f"Error extracting file {file_info.filename} from ZIP: {str(e)}")
                        continue
        
        return extracted_files
        
    except zipfile.BadZipFile:
        logger.error("Invalid ZIP file format")
        return []
    except Exception as e:
        logger.error(f"Error extracting ZIP: {str(e)}")
        logger.error(traceback.format_exc())
        return []


@router.post("/extract", response_model=ProcessResponse)
async def extract_bank_details(
    files: List[UploadFile] = File(...),
    header_config_id: Optional[int] = None,
    gemini_service: GeminiService = Depends(get_gemini_service),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Process uploaded PDF and image files and extract bank details
    
    Args:
        files: Uploaded PDF or image files (PDF, PNG, JPG, JPEG, WebP) or ZIP files containing these
        header_config_id: Optional header configuration ID to customize extraction fields
        gemini_service: Gemini AI service
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        ProcessResponse with operation results
    """
    try:
        logger.debug(f"Extract endpoint called with {len(files)} files and header_config_id={header_config_id}")
        
        if not files:
            logger.warning("No files provided")
            raise HTTPException(status_code=400, detail="No files selected")
        
        # Get header configuration if provided
        header_config = None
        if header_config_id:
            header_config = await get_header_config(header_config_id, get_user_id(current_user), db)
            if not header_config:
                logger.warning(f"Header configuration with ID {header_config_id} not found")
                raise HTTPException(status_code=404, detail="Header configuration not found")
            logger.debug(f"Using header configuration: {header_config.name}")
        
        total_records_added = 0
        all_results = []
        errors = []
        
        # Define allowed file extensions
        allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.zip']
        
        # Process each file
        for file in files:
            # Validate file
            if not file.filename:
                logger.warning("File has no filename")
                errors.append({"filename": "unknown", "error": "File has no filename"})
                continue
                
            # Check file extension
            file_ext = os.path.splitext(file.filename.lower())[-1]
            if file_ext not in allowed_extensions:
                logger.warning(f"File {file.filename} has unsupported extension: {file_ext}")
                errors.append({
                    "filename": file.filename, 
                    "error": f"Unsupported file format. Allowed formats: PDF, PNG, JPG, JPEG, WebP, ZIP"
                })
                continue
                
            # Secure the filename
            filename = os.path.splitext(file.filename)[0] # Keep original filename for secure_filename
            filename = secure_filename(filename) # Use secure_filename for consistency
            logger.debug(f"Processing file: {filename}")
            
            try:
                # Read file content
                file_content = await file.read()
                logger.debug(f"File {filename} read successfully, size: {len(file_content)} bytes")
                
                if len(file_content) == 0:
                    logger.warning(f"File {filename} is empty")
                    errors.append({"filename": filename, "error": "File is empty"})
                    continue
                
                # Handle ZIP files specially - extract and process all files
                if file_ext.lower() == '.zip':
                    logger.debug(f"Processing ZIP file: {filename}")
                    
                    # Extract files from ZIP
                    extracted_files = await extract_zip_files(file_content)
                    
                    if not extracted_files:
                        logger.warning(f"No valid files found in ZIP: {filename}")
                        errors.append({
                            "filename": filename,
                            "error": "No valid files found in the ZIP archive"
                        })
                        continue
                    
                    logger.debug(f"Found {len(extracted_files)} valid files in ZIP: {filename}")
                    
                    # Process each extracted file
                    zip_results = []
                    zip_errors = []
                    zip_records_added = 0
                    
                    for extracted_file in extracted_files:
                        extracted_filename = secure_filename(extracted_file['filename'])
                        extracted_data = extracted_file['data']
                        extracted_ext = extracted_file['ext']
                        
                        logger.debug(f"Processing extracted file: {extracted_filename} ({extracted_ext})")
                        
                        try:
                            # Extract bank details with Gemini
                            logger.debug(f"Calling Gemini API for file {extracted_filename}")
                            json_data = gemini_service.extract_bank_details(extracted_data, extracted_ext, header_config)
                            logger.debug(f"Gemini API returned JSON data for file {json_data}")
                            
                            # Save raw extraction data
                            logger.debug(f"Saving raw extraction data for file {extracted_filename}")
                            raw_result = await save_raw_extraction(get_user_id(current_user), extracted_filename, json_data)
                            if not raw_result['success']:
                                logger.warning(f"Failed to save raw extraction data: {raw_result.get('error')}")

                            # Add results to response - include the full JSON data
                            zip_results.append({
                                "source_pdf": extracted_filename,
                                "raw_data": json_data
                            })
                        except Exception as e:
                            logger.error(f"Error processing extracted file {extracted_filename}: {str(e)}")
                            logger.error(traceback.format_exc())
                            zip_errors.append({
                                "filename": extracted_filename,
                                "error": f"Processing error: {str(e)}"
                            })
                    
                    # Add ZIP processing results to overall results
                    total_records_added += zip_records_added
                    all_results.extend(zip_results)
                    errors.extend(zip_errors)
                    
                    logger.debug(f"Processed ZIP file {filename}: {len(zip_results)} files successful, {len(zip_errors)} files failed")
                    
                else:
                    # Process regular file (PDF, PNG, JPG, JPEG, WebP)
                    # Extract bank details with Gemini
                    logger.debug(f"Calling Gemini API for file {filename}")
                    json_data = gemini_service.extract_bank_details(file_content, file_ext, header_config)
                    logger.debug(f"Gemini API returned JSON data for file {filename}")
                    
                    # Save raw extraction data
                    logger.debug(f"Saving raw extraction data for file {filename} and data \n\n {json_data}")
                    raw_result = await save_raw_extraction(get_user_id(current_user), filename, json_data)
                    if not raw_result['success']:
                        logger.warning(f"Failed to save raw extraction data: {raw_result.get('error')}")
                    
                    # Add results to response - include the full JSON data
                    all_results.append({
                        "source_pdf": filename,
                        "raw_data": json_data
                    })
            except HTTPException as he:
                logger.error(f"HTTP Exception processing file {filename}: {str(he)}")
                errors.append({"filename": filename, "error": he.detail})
                continue
            except Exception as e:
                logger.error(f"Error processing file {filename}: {str(e)}")
                logger.error(traceback.format_exc())
                errors.append({"filename": filename, "error": f"Processing error: {str(e)}"})
                continue
        
        logger.debug(f"Extract endpoint completed with {total_records_added} total records added and {len(errors)} errors")
        
        # If no successful results and we have errors, return the first error
        if len(all_results) == 0 and len(errors) > 0:
            error_message = "Failed to process files: "
            if len(errors) == 1:
                error_message += errors[0]["error"]
            else:
                error_message += f"{len(errors)} files had errors"
            raise HTTPException(status_code=400, detail=error_message)
        
        # Return response with both results and errors
        return ProcessResponse(
            success=True,
            records_added=total_records_added,
            results=all_results,
            errors=errors
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
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
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
        processed_files = await get_processed_files(get_user_id(current_user), db)
        
        # Get total records
        total_records = await count_user_records(get_user_id(current_user), db)
        
        # Get all records
        records = await get_user_records(get_user_id(current_user), db)
        
        # Get raw extractions
        raw_extractions = await get_raw_extractions(get_user_id(current_user), db)
        
        # Convert records to dict for response
        results = []
        for record in records:
            # Check if record is a dict or an object
            if isinstance(record, dict):
                # It's already a dict (from DynamoDB)
                result_dict = {
                    'source_pdf': record.get('source_pdf', ''),
                    'account_number': record.get('account_number'),
                    'account_name': record.get('account_name'),
                    'bank_name': record.get('bank_name'),
                    'sort_code': record.get('sort_code'),
                    'iban': record.get('iban'),
                    'swift_code': record.get('swift_code'),
                    'routing_number': record.get('routing_number'),
                    'bsb_code': record.get('bsb_code'),
                    'branch_code': record.get('branch_code'),
                    'branch_address': record.get('branch_address'),
                    'account_type': record.get('account_type'),
                    'currency': record.get('currency'),
                    'balance': record.get('balance'),
                    'other_details': record.get('other_details'),
                    # Add a flag to indicate this is a structured record from the database
                    'is_structured_record': True
                }
            else:
                # It's an object (from SQLite)
                result_dict = {
                    'source_pdf': record.source_pdf if hasattr(record, 'source_pdf') else '',
                    'account_number': record.account_number if hasattr(record, 'account_number') else None,
                    'account_name': record.account_name if hasattr(record, 'account_name') else None,
                    'bank_name': record.bank_name if hasattr(record, 'bank_name') else None,
                    'sort_code': record.sort_code if hasattr(record, 'sort_code') else None,
                    'iban': record.iban if hasattr(record, 'iban') else None,
                    'swift_code': record.swift_code if hasattr(record, 'swift_code') else None,
                    'routing_number': record.routing_number if hasattr(record, 'routing_number') else None,
                    'bsb_code': record.bsb_code if hasattr(record, 'bsb_code') else None,
                    'branch_code': record.branch_code if hasattr(record, 'branch_code') else None,
                    'branch_address': record.branch_address if hasattr(record, 'branch_address') else None,
                    'account_type': record.account_type if hasattr(record, 'account_type') else None,
                    'currency': record.currency if hasattr(record, 'currency') else None,
                    'balance': record.balance if hasattr(record, 'balance') else None,
                    'other_details': record.other_details if hasattr(record, 'other_details') else None,
                    # Add a flag to indicate this is a structured record from the database
                    'is_structured_record': True
                }
            results.append(result_dict)
        
        # Create file info list
        files = []
        for filename in processed_files:
            files.append({
                "name": filename,
                "size": 0  # Size not available from DB
            })
        
        # Add raw extractions to results
        for extraction in raw_extractions:
            # Use dict.get() for safer access
            results.append({
                "source_pdf": extraction.get('source_pdf', 'Unknown'),
                "raw_data": extraction.get('raw_data', {}),
                "is_raw_extraction": True
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
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
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
        result = await clear_user_session(get_user_id(current_user), db)
        if result.get("success", False):
            return {"success": True, "records_deleted": result.get("records_deleted", 0)}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to clear session"))
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
    config_id: int = None,
    format: str = "csv",
    use_raw: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Download the CSV file with user's bank details
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        config_id: Header configuration ID (optional)
        format: File format (csv or xlsx)
        use_raw: Whether to use raw JSON data instead of structured records
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with CSV file
    """
    try:
        logger.debug(f"Download CSV endpoint called with config_id={config_id}, format={format}, use_raw={use_raw}")
        
        if use_raw:
            # Get raw extractions
            raw_extractions = await get_raw_extractions(get_user_id(current_user), db)
            
            if not raw_extractions:
                logger.warning("No raw extractions found for download")
                raise HTTPException(
                    status_code=400, 
                    detail="No raw extractions found. Please process some PDFs first."
                )
            
            logger.debug(f"Found {len(raw_extractions)} raw extractions for download")
            
            # Extract all bank details from raw extractions
            all_bank_details = []
            for extraction in raw_extractions:
                raw_data = extraction.get('raw_data', {})
                source_pdf = extraction.get('source_pdf', 'Unknown')
                extraction_date_str = extraction.get('extraction_date', '')
                
                # Handle extraction_date which could be a string or a datetime object
                if isinstance(extraction_date_str, str):
                    extraction_date = extraction_date_str
                elif hasattr(extraction_date_str, 'strftime'):
                    extraction_date = extraction_date_str.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    extraction_date = str(datetime.now())
                
                if 'bank_details' in raw_data and isinstance(raw_data['bank_details'], list):
                    for bank_detail in raw_data['bank_details']:
                        # Add source_pdf and extraction_date to each bank detail
                        bank_detail['source_pdf'] = source_pdf
                        bank_detail['extraction_date'] = extraction_date
                        all_bank_details.append(bank_detail)
                else:
                    # If no bank_details field, add the entire raw data as a record
                    record = {'source_pdf': source_pdf, 'extraction_date': extraction_date}
                    record.update(raw_data)
                    all_bank_details.append(record)
            
            if not all_bank_details:
                logger.warning("No bank details found in raw extractions")
                raise HTTPException(
                    status_code=400, 
                    detail="No bank details found in raw extractions."
                )
            
            # Generate file based on format
            if format.lower() == "xlsx":
                file_path, filename = generate_excel_file(all_bank_details)
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                filename = 'bank_details_raw.xlsx'
            else:
                file_path, filename = generate_csv_file(all_bank_details)
                mime_type = 'text/csv'
                filename = 'bank_details_raw.csv'
            
            # Add task to remove the file after the response is sent
            background_tasks.add_task(remove_temp_file, file_path)
            
            # Return the file
            return FileResponse(
                path=file_path,
                media_type=mime_type,
                filename=filename
            )
        else:
            # Original implementation for structured records
            # Get user records
            records = await get_user_records(get_user_id(current_user), db)
            
            if not records:
                logger.warning("No records found for download")
                raise HTTPException(
                    status_code=400, 
                    detail="No records found. Please process some PDFs first."
                )
            
            logger.debug(f"Found {len(records)} records for download")
            
            # Get header configuration
            header_config = None
            if config_id:
                logger.debug(f"Fetching header config with ID: {config_id}")
                header_config = await get_header_config(config_id, get_user_id(current_user), db)
                if not header_config:
                    logger.warning(f"Header configuration with ID {config_id} not found")
                    raise HTTPException(status_code=404, detail="Header configuration not found")
                
                # Handle header_config as either object or dict
                config_name = header_config.name if hasattr(header_config, 'name') else header_config.get('name', 'Unknown')
                config_mappings = header_config.header_mappings if hasattr(header_config, 'header_mappings') else header_config.get('header_mappings', {})
                logger.debug(f"Using header config: {config_name}, mappings: {config_mappings}")
            else:
                # Use default config
                logger.debug("No config_id provided, using default config")
                header_config = await ensure_default_config(get_user_id(current_user), db)
                
                # Handle header_config as either object or dict
                config_name = header_config.name if hasattr(header_config, 'name') else header_config.get('name', 'Default')
                config_mappings = header_config.header_mappings if hasattr(header_config, 'header_mappings') else header_config.get('header_mappings', {})
                logger.debug(f"Using default config: {config_name}, mappings: {config_mappings}")
            
            # Override format if specified in config
            config_format = header_config.file_format if hasattr(header_config, 'file_format') else header_config.get('file_format', 'csv')
            if format == "csv" and config_format != "csv":
                logger.debug(f"Overriding format from {format} to {config_format}")
                format = config_format
            
            # Convert records to dict
            records_dict = []
            for record in records:
                # Check if record is a dict or an object
                if isinstance(record, dict):
                    # It's already a dict (from DynamoDB)
                    record_dict = {
                        'source_pdf': record.get('source_pdf', ''),
                        'extraction_date': record.get('extraction_date', str(datetime.now())),
                        'account_number': record.get('account_number'),
                        'account_name': record.get('account_name'),
                        'bank_name': record.get('bank_name'),
                        'sort_code': record.get('sort_code'),
                        'iban': record.get('iban'),
                        'swift_code': record.get('swift_code'),
                        'routing_number': record.get('routing_number'),
                        'bsb_code': record.get('bsb_code'),
                        'branch_code': record.get('branch_code'),
                        'branch_address': record.get('branch_address'),
                        'account_type': record.get('account_type'),
                        'currency': record.get('currency'),
                        'balance': record.get('balance'),
                        'other_details': record.get('other_details')
                    }
                else:
                    # It's an object (from SQLite)
                    extraction_date = record.extraction_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(record, 'extraction_date') and record.extraction_date else str(datetime.now())
                    record_dict = {
                        'source_pdf': record.source_pdf if hasattr(record, 'source_pdf') else '',
                        'extraction_date': extraction_date,
                        'account_number': record.account_number if hasattr(record, 'account_number') else None,
                        'account_name': record.account_name if hasattr(record, 'account_name') else None,
                        'bank_name': record.bank_name if hasattr(record, 'bank_name') else None,
                        'sort_code': record.sort_code if hasattr(record, 'sort_code') else None,
                        'iban': record.iban if hasattr(record, 'iban') else None,
                        'swift_code': record.swift_code if hasattr(record, 'swift_code') else None,
                        'routing_number': record.routing_number if hasattr(record, 'routing_number') else None,
                        'bsb_code': record.bsb_code if hasattr(record, 'bsb_code') else None,
                        'branch_code': record.branch_code if hasattr(record, 'branch_code') else None,
                        'branch_address': record.branch_address if hasattr(record, 'branch_address') else None,
                        'account_type': record.account_type if hasattr(record, 'account_type') else None,
                        'currency': record.currency if hasattr(record, 'currency') else None,
                        'balance': record.balance if hasattr(record, 'balance') else None,
                        'other_details': record.other_details if hasattr(record, 'other_details') else None
                    }
                records_dict.append(record_dict)
            
            # Apply header mapping
            mapped_records = apply_header_mapping(records_dict, config_mappings)
            
            # Get custom headers string if provided in header config
            custom_headers = None
            if config_mappings:
                custom_headers = ','.join(config_mappings.values())
            
            # Generate file based on format
            if format.lower() == "xlsx":
                file_path, filename = generate_excel_file(mapped_records, custom_headers)
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                file_path, filename = generate_csv_file(mapped_records, custom_headers)
                mime_type = 'text/csv'
            
            # Add task to remove the file after the response is sent
            background_tasks.add_task(remove_temp_file, file_path)
            
            # Return the file
            return FileResponse(
                path=file_path,
                media_type=mime_type,
                filename=filename
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error in download-csv endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/csv")
async def export_csv(
    background_tasks: BackgroundTasks,
    token: str = None,
    config_id: int = None,
    format: str = "csv",
    use_raw: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Export CSV endpoint (alias for download-csv)
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        token: Authentication token (optional)
        config_id: Header configuration ID (optional)
        format: File format (csv or xlsx)
        use_raw: Whether to use raw JSON data instead of structured records
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with CSV file
    """
    # Just call the existing download-csv endpoint
    return await download_csv(
        background_tasks=background_tasks,
        config_id=config_id,
        format=format,
        use_raw=use_raw,
        db=db,
        current_user=current_user
    )


@router.get("/check_file/{filename}")
async def check_file(
    filename: str,
    current_user: UserDB = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_async_db)
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
        total_records = await count_user_records(get_user_id(current_user), db)
        return {"exists": total_records > 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download-json")
async def download_json(
    background_tasks: BackgroundTasks,
    use_raw: bool = True,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Download the JSON file with user's bank details
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        use_raw: Whether to use raw JSON data instead of structured records
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with JSON file
    """
    try:
        logger.debug(f"Download JSON endpoint called with use_raw={use_raw}")
        
        if use_raw:
            # Get raw extractions
            raw_extractions = await get_raw_extractions(get_user_id(current_user), db)
            
            if not raw_extractions:
                logger.warning("No raw extractions found for download")
                raise HTTPException(
                    status_code=400, 
                    detail="No raw extractions found. Please process some PDFs first."
                )
            
            logger.debug(f"Found {len(raw_extractions)} raw extractions for download")
            
            # Extract all bank details from raw extractions
            all_bank_details = []
            for extraction in raw_extractions:
                raw_data = extraction.get('raw_data', {})
                source_pdf = extraction.get('source_pdf', 'Unknown')
                extraction_date_str = extraction.get('extraction_date', '')
                
                # Handle extraction_date which could be a string or a datetime object
                if isinstance(extraction_date_str, str):
                    extraction_date = extraction_date_str
                elif hasattr(extraction_date_str, 'strftime'):
                    extraction_date = extraction_date_str.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    extraction_date = str(datetime.now())
                
                if 'bank_details' in raw_data and isinstance(raw_data['bank_details'], list):
                    for bank_detail in raw_data['bank_details']:
                        # Add source_pdf and extraction_date to each bank detail
                        bank_detail['source_pdf'] = source_pdf
                        bank_detail['extraction_date'] = extraction_date
                        all_bank_details.append(bank_detail)
                else:
                    # If no bank_details field, add the entire raw data as a record
                    record = {'source_pdf': source_pdf, 'extraction_date': extraction_date}
                    record.update(raw_data)
                    all_bank_details.append(record)
            
            if not all_bank_details:
                logger.warning("No bank details found in raw extractions")
                raise HTTPException(
                    status_code=400, 
                    detail="No bank details found in raw extractions."
                )
            
            # Generate JSON file
            file_path, filename = generate_json_file(all_bank_details)
            
            # Add task to remove the file after the response is sent
            background_tasks.add_task(remove_temp_file, file_path)
            
            # Return the JSON file
            return FileResponse(
                path=file_path,
                media_type='application/json',
                filename=filename
            )
        else:
            # Get structured records
            records = await get_user_records(get_user_id(current_user), db)
            
            if not records:
                logger.warning("No records found for download")
                raise HTTPException(
                    status_code=400, 
                    detail="No records found. Please process some PDFs first."
                )
            
            logger.debug(f"Found {len(records)} records for download")
            
            # Convert records to dict
            records_dict = []
            for record in records:
                # Check if record is a dict or an object
                if isinstance(record, dict):
                    # It's already a dict (from DynamoDB)
                    record_dict = {
                        'source_pdf': record.get('source_pdf', ''),
                        'extraction_date': record.get('extraction_date', str(datetime.now())),
                        'account_number': record.get('account_number'),
                        'account_name': record.get('account_name'),
                        'bank_name': record.get('bank_name'),
                        'sort_code': record.get('sort_code'),
                        'iban': record.get('iban'),
                        'swift_code': record.get('swift_code'),
                        'routing_number': record.get('routing_number'),
                        'bsb_code': record.get('bsb_code'),
                        'branch_code': record.get('branch_code'),
                        'branch_address': record.get('branch_address'),
                        'account_type': record.get('account_type'),
                        'currency': record.get('currency'),
                        'balance': record.get('balance'),
                        'other_details': record.get('other_details')
                    }
                else:
                    # It's an object (from SQLite)
                    extraction_date = record.extraction_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(record, 'extraction_date') and record.extraction_date else str(datetime.now())
                    record_dict = {
                        'source_pdf': record.source_pdf if hasattr(record, 'source_pdf') else '',
                        'extraction_date': extraction_date,
                        'account_number': record.account_number if hasattr(record, 'account_number') else None,
                        'account_name': record.account_name if hasattr(record, 'account_name') else None,
                        'bank_name': record.bank_name if hasattr(record, 'bank_name') else None,
                        'sort_code': record.sort_code if hasattr(record, 'sort_code') else None,
                        'iban': record.iban if hasattr(record, 'iban') else None,
                        'swift_code': record.swift_code if hasattr(record, 'swift_code') else None,
                        'routing_number': record.routing_number if hasattr(record, 'routing_number') else None,
                        'bsb_code': record.bsb_code if hasattr(record, 'bsb_code') else None,
                        'branch_code': record.branch_code if hasattr(record, 'branch_code') else None,
                        'branch_address': record.branch_address if hasattr(record, 'branch_address') else None,
                        'account_type': record.account_type if hasattr(record, 'account_type') else None,
                        'currency': record.currency if hasattr(record, 'currency') else None,
                        'balance': record.balance if hasattr(record, 'balance') else None,
                        'other_details': record.other_details if hasattr(record, 'other_details') else None
                    }
                records_dict.append(record_dict)
            
            # Generate JSON file
            file_path, filename = generate_json_file(records_dict)
            
            # Add task to remove the file after the response is sent
            background_tasks.add_task(remove_temp_file, file_path)
            
            # Return the JSON file
            return FileResponse(
                path=file_path,
                media_type='application/json',
                filename=filename
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error in download-json endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e)) 


@router.get("/export/json")
async def export_json(
    background_tasks: BackgroundTasks,
    token: str = None,
    use_raw: bool = True,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Export JSON endpoint (alias for download-json)
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        token: Authentication token (optional)
        use_raw: Whether to use raw JSON data instead of structured records
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with JSON file
    """
    # Just call the existing download-json endpoint
    return await download_json(
        background_tasks=background_tasks,
        use_raw=use_raw,
        db=db,
        current_user=current_user
    ) 
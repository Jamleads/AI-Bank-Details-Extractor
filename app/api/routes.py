"""
API routes for bank details extraction
"""
import os
import io
import zipfile
import traceback
import logging
import json
import os
import tempfile
import uuid
from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request, BackgroundTasks, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.utils import secure_filename
from app.db.database import get_async_db
from app.models.user import UserDB
from app.models.bank_details import BankDetail
from app.models.response import ProcessResponse, SessionStatus
from app.models.file_upload import FileUploads, FileUploadRequest, PresignedUrlResponse, PresignedUrlsResponse, S3FileReference, ExtractRequest, ProcessFileRequest
from app.services.gemini_service import GeminiService
from app.services.storage_adapter import storage
from app.utils.auth import get_current_user_required, get_user_id
from app.utils.file import generate_csv_file, generate_json_file
from app.services.header_config_service import apply_header_mapping
from app.db.operations import (
    save_bank_details, 
    count_user_records,
    save_raw_extraction,
    get_raw_extractions,
    clear_user_session
)
from app.db.header_config import get_header_config, ensure_default_config
from datetime import datetime
from app.core.admin_config import is_admin_email
from app.db.adapter import db
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from stream_unzip import async_stream_unzip
from asyncio import Semaphore, gather, create_task

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/api", tags=["document-extraction"])

# Include payment router
# router.include_router(payment_router, prefix="/payment", tags=["payment"]) # This line was removed as per the new_code, as payment_router is no longer imported.

# Templates
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


# Dependencies
def get_gemini_service():
    """Dependency for Gemini service"""
    return GeminiService()


@router.get("/", include_in_schema=False)
async def index(request: Request):
    """Main page"""
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
                # Skip directories and system files
                if file_info.filename.endswith('/') or is_system_file(file_info.filename):
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

async def extract_zip_files_async(zip_data: bytes) -> List[Dict[str, Any]]:
    async def byte_stream():
        yield zip_data

    extracted = []
    async for filename, size, chunks in async_stream_unzip(byte_stream()):
        # Decode filename if it's bytes
        if isinstance(filename, bytes):
            filename = filename.decode('utf-8')
            
        ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        ext = f".{ext}"

        if ext in {'.pdf', '.png', '.jpg', '.jpeg', '.webp'}:
            data = b''
            async for chunk in chunks:
                # Ensure chunk is bytes
                if isinstance(chunk, str):
                    chunk = chunk.encode()
                data += chunk

            if len(data) > 100:
                extracted.append({'filename': filename, 'data': data, 'ext': ext})

    return extracted

@router.post("/extract", response_model=ProcessResponse, description="Extract bank details from uploaded files", include_in_schema=False)
async def extract_bank_details(
    files: List[UploadFile] = File(...),
    header_config_id: Optional[str] = Form(None),
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
        logger.debug(f"Debug: header_config_id type: {type(header_config_id)}, value: '{header_config_id}', repr: {repr(header_config_id)}")
        
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
            logger.debug(f"Using header configuration: {getattr(header_config, 'name', 'unknown')}")
        
        total_records_added = 0
        all_results = []
        errors = []
        
        # Define allowed file extensions
        allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.zip']
        
        # Concurrency control
        MAX_CONCURRENCY = 6
        sem = Semaphore(MAX_CONCURRENCY)
        user_id = get_user_id(current_user)

        async def handle_one_file(proc_filename: str, file_bytes: bytes, ext: str) -> Dict[str, Any]:
            """Process a single file blob under semaphore and return either ok/err dict."""
            async with sem:
                try:
                    logger.debug(f"Processing file: {proc_filename} ({len(file_bytes)} bytes, {ext})")
                    json_data = await gemini_service.extract_bank_details_async(file_bytes, ext, header_config)
                    # Save raw extraction data
                    raw_result = await save_raw_extraction(user_id, proc_filename, json_data)
                    if not raw_result.get('success', False):
                        logger.warning(f"Failed to save raw extraction data for {proc_filename}: {raw_result.get('error')}")
                    logger.debug(f"Successfully processed file: {proc_filename}")
                    return {"ok": {"source_pdf": proc_filename, "raw_data": json_data}}
                except HTTPException as he:
                    logger.error(f"HTTP Exception processing file {proc_filename}: {str(he)}")
                    return {"err": {"filename": proc_filename, "error": he.detail}}
                except Exception as e:
                    logger.error(f"Error processing file {proc_filename}: {str(e)}")
                    logger.error(traceback.format_exc())
                    return {"err": {"filename": proc_filename, "error": f"Processing error: {str(e)}"}}
        
        # Build tasks
        tasks = []
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
                
            # Secure the filename (without extension)
            filename_base = os.path.splitext(file.filename)[0]
            safe_filename = secure_filename(filename_base)
            
            # Read file content
            try:
                file_content = await file.read()
                logger.debug(f"Read file: {safe_filename} ({len(file_content)} bytes, {file_ext})")
            except Exception as e:
                logger.error(f"Error reading file {safe_filename}: {str(e)}")
                errors.append({"filename": safe_filename, "error": f"Failed to read file: {str(e)}"})
                continue
            
            if len(file_content) == 0:
                logger.warning(f"File {safe_filename} is empty")
                errors.append({"filename": safe_filename, "error": "File is empty"})
                continue
            
            if file_ext.lower() == '.zip':
                logger.debug(f"Processing ZIP file (streaming): {safe_filename}")
                # Stream unzip and schedule processing for each entry as soon as it's ready
                async def byte_stream():
                    yield file_content

                valid_count = 0
                async for z_name, z_size, z_chunks in async_stream_unzip(byte_stream()):
                    # Normalize name
                    if isinstance(z_name, bytes):
                        z_name = z_name.decode('utf-8')
                    extracted_ext = f".{z_name.rsplit('.', 1)[-1].lower()}" if '.' in z_name else ''

                    if extracted_ext not in {'.pdf', '.png', '.jpg', '.jpeg', '.webp'}:
                        continue

                    # Assemble this entry only
                    buf = bytearray()
                    async for chunk in z_chunks:
                        if isinstance(chunk, str):
                            chunk = chunk.encode()
                        buf.extend(chunk)

                    if len(buf) > 100:
                        extracted_filename = secure_filename(z_name)
                        logger.debug(f"Extracted from ZIP: {extracted_filename} ({len(buf)} bytes, {extracted_ext})")
                        # Start processing immediately
                        tasks.append(create_task(handle_one_file(extracted_filename, bytes(buf), extracted_ext)))
                        valid_count += 1

                if valid_count == 0:
                    logger.warning(f"No valid files found in ZIP: {safe_filename}")
                    errors.append({
                        "filename": safe_filename,
                        "error": "No valid files found in the ZIP archive"
                    })
                    continue
                else:
                    logger.debug(f"Found {valid_count} valid files in ZIP: {safe_filename}")
            else:
                # Schedule regular file processing
                tasks.append(create_task(handle_one_file(safe_filename, file_content, file_ext)))
        
        # Execute tasks with bounded concurrency
        if tasks:
            logger.debug(f"Executing {len(tasks)} processing tasks with max concurrency {MAX_CONCURRENCY}")
            results_list = await gather(*tasks, return_exceptions=True)
            for item in results_list:
                if isinstance(item, Exception):
                    errors.append({"filename": "unknown", "error": f"Processing error: {str(item)}"})
                elif isinstance(item, dict):
                    if 'ok' in item:
                        all_results.append(item['ok'])
                    elif 'err' in item:
                        errors.append(item['err'])
        
        logger.debug(f"Extract endpoint completed: {len(all_results)} successful, {len(errors)} errors")
        
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


@router.get("/session-status", response_model=SessionStatus, description="Get the current session status")
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
        user_id = get_user_id(current_user)
        logger.debug(f"Getting session status for user_id: {user_id}")
        
        # Get raw extractions
        raw_extractions = await get_raw_extractions(user_id, db)
        logger.debug(f"Found {len(raw_extractions)} raw extraction records")
        
        # Debug: Log the structure of the first record
        if raw_extractions:
            logger.debug(f"First raw extraction record structure: {raw_extractions[0]}")
            first_raw_data = raw_extractions[0].get('raw_data', {})
            logger.debug(f"First raw_data structure: {first_raw_data}")
            logger.debug(f"Raw_data keys: {list(first_raw_data.keys()) if isinstance(first_raw_data, dict) else 'Not a dict'}")
        
        # Return the raw extraction data exactly as it was extracted
        results = []
        for record in raw_extractions:
            # Get the raw_data which contains all the extracted information
            raw_data = record.get('raw_data', {})
            
            # Create base record with metadata
            base_record = {
                'source_pdf': record.get('source_pdf', ''),
                'extraction_date': record.get('created_at', ''),
            }
            
            # If raw_data is empty or None, skip this record
            if not raw_data:
                continue
            
            # If raw_data has a bank_details list, process each item
            if isinstance(raw_data, dict) and 'bank_details' in raw_data and isinstance(raw_data['bank_details'], list):
                for bank_detail in raw_data['bank_details']:
                    if isinstance(bank_detail, dict):
                        # Merge base record with bank detail
                        result_record = {**base_record, **bank_detail}
                        results.append(result_record)
            else:
                # If raw_data doesn't have bank_details structure, use it directly
                if isinstance(raw_data, dict):
                    # Merge base record with all raw data
                    result_record = {**base_record, **raw_data}
                    results.append(result_record)
                else:
                    # If raw_data is not a dict, create a record with just the base info
                    base_record['raw_content'] = str(raw_data)
                    results.append(base_record)
        
        return SessionStatus(
            results=results,
            total_records=len(results)
        )
    except Exception as e:
        logger.error(f"Error in session-status endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-session", include_in_schema=False)
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
def is_system_file(file_path: str) -> bool:
    """
    Check if a file is a system file that should be ignored
    
    Args:
        file_path: The file path to check
        
    Returns:
        True if it's a system file, False otherwise
    """
    system_patterns = [
        # macOS system files
        '__MACOSX',
        '.DS_Store',
        '._.DS_Store',
        '._',
        '.fseventsd',
        '.Spotlight-V100',
        '.TemporaryItems',
        '.Trashes',
        '.VolumeIcon.icns',
        '.com.apple.',
        
        # Windows system files
        'Thumbs.db',
        'ehthumbs.db',
        'Desktop.ini',
        '$RECYCLE.BIN',
        'System Volume Information',
        
        # Linux system files
        '.directory',
        '.trash',
        
        # General hidden files and directories
        '.git',
        '.svn',
        '.hg',
        'node_modules',
        '.env'
    ]
    
    # Convert to lowercase for case-insensitive matching
    path_lower = file_path.lower()
    
    # Check if the path contains any system patterns
    for pattern in system_patterns:
        if pattern.lower() in path_lower:
            return True
    
    # Check if it's a hidden file (starts with .)
    file_name = file_path.split('/')[-1]
    if file_name.startswith('.'):
        return True
    
    # Check if it's in a hidden directory
    if '/.' in file_path:
        return True
    
    return False


def remove_temp_file(file_path: str):
    """Remove temporary file after response is sent"""
    try:
        os.unlink(file_path)
        logger.debug(f"Temporary file {file_path} removed")
    except Exception as e:
        logger.error(f"Error removing temporary file {file_path}: {str(e)}")


@router.get("/download-csv", include_in_schema=False)
async def download_csv(
    background_tasks: BackgroundTasks,
    config_id: Union[int, str] = None,
    format: str = "csv",
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Download the CSV file with user's bank details
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        config_id: Header configuration ID (optional, can be integer or string UUID)
        format: File format (csv or xlsx)
        custom_headers: Custom headers as comma-separated string
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with CSV file
    """
    try:
        logger.debug(f"Download CSV endpoint called with config_id={config_id}, format={format}")
        
        # Get header configuration if provided
        header_config = None
        header_mappings = None
        
        if config_id:
            try:
                header_config = await get_header_config(config_id, get_user_id(current_user), db)
                if header_config:
                    # Handle both object and dictionary access
                    if isinstance(header_config, dict):
                        header_mappings = header_config.get('header_mappings', {})
                    else:
                        header_mappings = header_config.header_mappings if hasattr(header_config, 'header_mappings') else {}
                    
                    logger.debug(f"Using header configuration: {header_config}")
                else:
                    logger.warning(f"Header configuration with ID {config_id} not found")
            except Exception as e:
                logger.error(f"Error getting header configuration: {str(e)}")

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
        
        # Apply header mappings if available
        if header_mappings:
            if "source_pdf" not in header_mappings.keys():
                header_mappings["source_pdf"] = "source_pdf"
            if "extraction_date" not in header_mappings.keys():
                header_mappings["extraction_date"] = "extraction_date"
            mapped_records = []
            for record in all_bank_details:
                mapping_record = {}
                for r in record:
                    if r in header_mappings.keys():
                        mapping_record[header_mappings[r]] = record[r]
                        continue
                mapped_records.append(mapping_record)
            
            all_bank_details = mapped_records

        # Generate CSV file
        file_path, filename = generate_csv_file(all_bank_details)
        
        filename = f'bank_details_raw.{format}'

        mime_type = 'text/csv' if format == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
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


@router.get("/export/csv", include_in_schema=False)
async def export_csv(
    background_tasks: BackgroundTasks,
    token: str = None,
    config_id: Union[int, str] = None,
    format: str = "csv",
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Export CSV endpoint (alias for download-csv)
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        token: Authentication token (optional)
        config_id: Header configuration ID (optional, can be integer or string UUID)
        format: File format (csv or xlsx)
        custom_headers: Custom headers as comma-separated string
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
        db=db,
        current_user=current_user
    )


@router.get("/check_file/{filename}", include_in_schema=False)
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


@router.get("/download-json", include_in_schema=False)
async def download_json(
    background_tasks: BackgroundTasks,
    config_id: Union[int, str] = None,
    use_raw: bool = True,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Download the JSON file with user's bank details
    
    Args:
        background_tasks: FastAPI BackgroundTasks
        config_id: Header configuration ID (optional, can be integer or string UUID)
        use_raw: Whether to use raw JSON data instead of structured records
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with JSON file
    """
    try:
        logger.debug(f"Download JSON endpoint called with use_raw={use_raw}")
        
        header_config = None
        header_mappings = None
        
        if config_id:
            try:
                header_config = await get_header_config(config_id, get_user_id(current_user), db)
                if header_config:
                    # Handle both object and dictionary access
                    if isinstance(header_config, dict):
                        header_mappings = header_config.get('header_mappings', {})
                    else:
                        header_mappings = header_config.header_mappings if hasattr(header_config, 'header_mappings') else {}
                    
                    logger.debug(f"Using header configuration: {header_config}")
                else:
                    logger.warning(f"Header configuration with ID {config_id} not found")
            except Exception as e:
                logger.error(f"Error getting header configuration: {str(e)}")


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
        
        if header_mappings:
            if "source_pdf" not in header_mappings.keys():
                header_mappings["source_pdf"] = "source_pdf"
            if "extraction_date" not in header_mappings.keys():
                header_mappings["extraction_date"] = "extraction_date"
            mapped_records = []
            for record in all_bank_details:
                mapping_record = {}
                for r in record:
                    if r in header_mappings.keys():
                        mapping_record[header_mappings[r]] = record[r]
                        continue
                mapped_records.append(mapping_record)
            
            all_bank_details = mapped_records

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
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error in download-json endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e)) 


@router.get("/export/json", include_in_schema=False)
async def export_json(
    background_tasks: BackgroundTasks,
    token: str = None,
    config_id: Union[int, str] = None,
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
        config_id=config_id,
        use_raw=use_raw,
        db=db,
        current_user=current_user
    ) 


@router.get("/user/is-admin", include_in_schema=False)
async def check_is_admin(
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Check if the current user is an admin
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dictionary with is_admin status
    """
    is_admin = False
    if current_user:
        # Handle both object and dictionary access
        email = current_user.get('email') if isinstance(current_user, dict) else getattr(current_user, 'email', None)
        if email:
            is_admin = is_admin_email(email)
    return {"is_admin": is_admin} 


@router.get("/user/api-keys", include_in_schema=False)
async def get_user_api_keys(
    current_user: UserDB = Depends(get_current_user_required)
):
    """Get all API keys for the current user"""
    api_keys = db.get_api_key_by_user_id(get_user_id(current_user))
    return {"api_keys": api_keys}


@router.post("/user/api-keys", include_in_schema=False)
async def create_user_api_key(
    current_user: UserDB = Depends(get_current_user_required)
):
    """Create a new API key for the current user"""
    api_key = db.create_api_key(get_user_id(current_user))
    return {"api_key": api_key}


@router.put("/user/api-keys/{api_key}/status", include_in_schema=False)
async def update_api_key_status(
    api_key: str,
    status: str,
    current_user: UserDB = Depends(get_current_user_required)
):
    """Update API key status (active/inactive)"""
    # Verify the API key belongs to the current user
    key_data = db.get_api_key(api_key)
    if not key_data or key_data.get('user_id') != get_user_id(current_user):
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Only allow valid status values
    if status not in ['active', 'inactive']:
        raise HTTPException(status_code=400, detail="Invalid status value")
    
    updated_key = db.update_api_key_status(api_key, status)
    return {"api_key": updated_key} 


# endpoint that returns a number presigned urls to the s3 bucket (legacy)
@router.get("/user/presigned-urls", include_in_schema=False)
async def get_presigned_urls(
    filesUploads: FileUploads,
    current_user: UserDB = Depends(get_current_user_required),
):
    """Get presigned URLs for the current user (legacy)"""
    presigned_urls = []
    # save the presigned urls to the database
    for file_upload in filesUploads.file_uploads:
        presigned_url = storage.generate_presigned_url(get_user_id(current_user))
        presigned_urls.append(presigned_url)
    
    return {"presigned_urls": presigned_urls}


@router.post("/request-presigned-urls", response_model=PresignedUrlsResponse, description="Request presigned URLs for file uploads with validation")
async def request_presigned_urls(
    file_requests: List[FileUploadRequest],
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Generate presigned URLs for file uploads with validation
    
    Args:
        file_requests: List of file upload requests with metadata
        current_user: Current authenticated user
        
    Returns:
        Dict containing presigned URL data for each file
    """
    try:
        logger.debug(f"Request presigned URLs for {len(file_requests)} files")
        
        # Validate file limits
        if len(file_requests) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 files allowed")
        
        if not file_requests:
            raise HTTPException(status_code=400, detail="No files specified")
        
        # Check for ZIP file restrictions
        zip_files = [f for f in file_requests if f.filename.lower().endswith('.zip')]
        if zip_files:
            if len(zip_files) > 1 or len(file_requests) > 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Only one ZIP file allowed, no other files can be selected with ZIP"
                )
        
        # Validate file types
        allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.zip']
        for file_req in file_requests:
            file_ext = os.path.splitext(file_req.filename)[1].lower()
            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
                )
        
        # Generate presigned URLs
        user_id = str(get_user_id(current_user))
        presigned_data = []
        
        for file_req in file_requests:
            # Generate presigned URL with metadata
            url_data = storage.generate_presigned_url_with_metadata(
                user_id=user_id,
                filename=file_req.filename,
                content_type=file_req.content_type,
                expiration=3600  # 1 hour
            )
            
            if not url_data:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate presigned URL for {file_req.filename}"
                )
            
            presigned_data.append(PresignedUrlResponse(
                file_id=str(uuid.uuid4()),
                filename=file_req.filename,
                presigned_url=url_data['presigned_url'],
                file_key=url_data['file_key'],
                content_type=file_req.content_type
            ))
        
        logger.debug(f"Generated {len(presigned_data)} presigned URLs successfully")
        return PresignedUrlsResponse(presigned_urls=presigned_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating presigned URLs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process", description="Process a single file from S3", include_in_schema=False)
async def process_single_file(
    process_request: ProcessFileRequest,
    gemini_service: GeminiService = Depends(get_gemini_service),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Process a single file from S3 (for cloud concurrent processing)
    
    Args:
        process_request: File processing request with S3 reference
        gemini_service: Gemini AI service
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Processing result with success/error status
    """
    try:
        logger.debug(f"Processing single file: {process_request.file_ref.filename}")
        
        # Using storage adapter instead of direct S3Service
        user_id = get_user_id(current_user)
        file_ref = process_request.file_ref
        
        # Download file from cloud storage
        download_result = storage.download_file(file_ref.file_key)
        if not download_result:
            raise HTTPException(
                status_code=404, 
                detail=f"File not found in S3: {file_ref.file_key}"
            )
        
        file_data, content_type = download_result
        
        # Get header configuration if provided
        header_config = None
        if process_request.header_config_id:
            header_config = await get_header_config(
                process_request.header_config_id, 
                user_id, 
                db
            )
        
        # Determine file extension
        file_ext = os.path.splitext(file_ref.filename)[1].lower()
        
        # Extract bank details using Gemini
        json_data = await gemini_service.extract_bank_details_async(
            file_data, file_ext, header_config
        )
        
        # Save raw extraction data
        raw_result = await save_raw_extraction(user_id, file_ref.filename, json_data)
        if not raw_result.get('success', False):
            logger.warning(f"Failed to save raw extraction data for {file_ref.filename}: {raw_result.get('error')}")
        
        # Clean up cloud storage file after processing
        cleanup_success = storage.delete_file(file_ref.file_key)
        if not cleanup_success:
            logger.warning(f"Failed to clean up cloud storage file: {file_ref.file_key}")
        
        logger.debug(f"Successfully processed file: {file_ref.filename}")
        return {
            "success": True,
            "file_id": file_ref.file_id,
            "filename": file_ref.filename,
            "raw_data": json_data
        }
        
    except HTTPException as he:
        logger.error(f"HTTP Exception processing file {process_request.file_ref.filename}: {str(he)}")
        return {
            "success": False,
            "file_id": process_request.file_ref.file_id,
            "filename": process_request.file_ref.filename,
            "error": he.detail
        }
    except Exception as e:
        logger.error(f"Error processing file {process_request.file_ref.filename}: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "file_id": process_request.file_ref.file_id,
            "filename": process_request.file_ref.filename,
            "error": f"Processing error: {str(e)}"
        }


@router.post("/extract-new", response_model=ProcessResponse, description="Extract bank details from S3-uploaded files")
async def extract_bank_details_new(
    extract_request: ExtractRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Extract bank details from S3-uploaded files using new architecture
    
    Args:
        extract_request: Request containing S3 file references
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        ProcessResponse with operation results
    """
    try:
        logger.debug(f"Extract-new endpoint called with {len(extract_request.files)} files")
        
        if not extract_request.files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Import environment detection
        from app.utils.environment import detect_cloud_environment
        
        # Detect processing mode
        user_id = get_user_id(current_user)
        
        logger.info(f"Processing {len(extract_request.files)} files in local mode")
        
        results = await process_files_locally(extract_request, user_id, db)
        
        logger.debug(f"Extract-new endpoint completed: {len(results.results)} successful, {len(results.errors)} errors")
        return results
        
    except HTTPException as he:
        logger.error(f"HTTP Exception in extract-new endpoint: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"Unhandled exception in extract-new endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


async def process_files_locally(
    extract_request: ExtractRequest,
    user_id: int,
    db: AsyncSession
) -> ProcessResponse:
    """Process files using local concurrent processing"""
    
    logger.debug(f"Processing {len(extract_request.files)} files in local mode")
    
    from asyncio import create_task, Semaphore, gather
    
    # Lower concurrency for local development
    MAX_CONCURRENCY = 6
    sem = Semaphore(MAX_CONCURRENCY)
    
    async def process_one_file(file_ref: S3FileReference) -> Dict[str, Any]:
        """Process a single file with semaphore control"""
        async with sem:
            try:
                # Using storage adapter instead of direct S3Service
                gemini_service = GeminiService()
                
                # Download file from cloud storage
                download_result = storage.download_file(file_ref.file_key)
                if not download_result:
                    return {
                        "success": False,
                        "file_id": file_ref.file_id,
                        "filename": file_ref.filename,
                        "error": f"File not found in S3: {file_ref.file_key}"
                    }
                
                file_data, content_type = download_result
                
                # Get header configuration if provided
                header_config = None
                if extract_request.header_config_id:
                    header_config = await get_header_config(
                        extract_request.header_config_id, 
                        user_id, 
                        db
                    )
                
                # Determine file extension
                file_ext = os.path.splitext(file_ref.filename)[1].lower()
                
                # Extract bank details using Gemini
                json_data = await gemini_service.extract_bank_details_async(
                    file_data, file_ext, header_config
                )
                
                # Save raw extraction data
                raw_result = await save_raw_extraction(user_id, file_ref.filename, json_data)
                if not raw_result.get('success', False):
                    logger.warning(f"Failed to save raw extraction data for {file_ref.filename}")
                
                # Clean up cloud storage file after processing
                storage.delete_file(file_ref.file_key)
                
                return {
                    "success": True,
                    "file_id": file_ref.file_id,
                    "filename": file_ref.filename,
                    "raw_data": json_data
                }
                
            except Exception as e:
                logger.error(f"Error processing file {file_ref.filename}: {str(e)}")
                return {
                    "success": False,
                    "file_id": file_ref.file_id,
                    "filename": file_ref.filename,
                    "error": str(e)
                }
    
    # Create tasks for all files
    tasks = [create_task(process_one_file(file_ref)) for file_ref in extract_request.files]
    
    # Execute all tasks concurrently
    results = await gather(*tasks, return_exceptions=True)
    
    # Process results
    successful_results = []
    errors = []
    
    for result in results:
        if isinstance(result, Exception):
            errors.append({"filename": "unknown", "error": str(result)})
        elif result.get("success"):
            successful_results.append(result)
        else:
            errors.append({
                "filename": result.get("filename", "unknown"),
                "error": result.get("error", "Processing failed")
            })
    
    return ProcessResponse(
        success=len(successful_results) > 0,
        records_added=len(successful_results),
        results=successful_results,
        errors=errors
    )


@router.get("/debug/raw-data", include_in_schema=False)
async def debug_raw_data(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Debug endpoint to inspect raw data structure
    """
    try:
        raw_extractions = await get_raw_extractions(get_user_id(current_user), db)
        
        debug_info = {
            "total_records": len(raw_extractions),
            "sample_records": []
        }
        
        # Show first 3 records for inspection
        for i, record in enumerate(raw_extractions[:3]):
            debug_record = {
                "record_index": i,
                "record_keys": list(record.keys()),
                "source_pdf": record.get('source_pdf'),
                "raw_data_type": type(record.get('raw_data', {})).__name__,
                "raw_data_keys": list(record.get('raw_data', {}).keys()) if isinstance(record.get('raw_data'), dict) else "Not a dict",
                "raw_data_sample": record.get('raw_data', {})
            }
            debug_info["sample_records"].append(debug_record)
        
        return debug_info
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        return {"error": str(e)}


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
from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request, BackgroundTasks, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.utils import secure_filename
from app.db.database import get_async_db
from app.models.user import UserDB
from app.models.bank_details import BankDetail
from app.models.response import ProcessResponse, SessionStatus
from app.models.file_upload import FileUploads
from app.services.gemini_service import GeminiService
from app.services.s3_service import S3Service
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
from app.db.dynamodb import DynamoDBService
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

@router.post("/extract", response_model=ProcessResponse, description="Extract bank details from uploaded files")
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
        # Get raw extractions
        raw_extractions = await get_raw_extractions(get_user_id(current_user), db)
        # Convert records to dict for response
        results = []
        for record in raw_extractions:
        
            for bank_detail in record.get('raw_data', {}).get('bank_details', []):
                result_dict = {
                    'source_pdf': record.get('source_pdf', ''),
                    'account_number': bank_detail.get('account_number'),
                    'account_name': bank_detail.get('account_name'),
                    'bank_name': bank_detail.get('bank_name'),
                    'sort_code': bank_detail.get('sort_code'),
                    'iban': bank_detail.get('iban'),
                    'swift_code': bank_detail.get('swift_code'),
                    'routing_number': bank_detail.get('routing_number'),
                    'bsb_code': bank_detail.get('bsb_code'),
                    'branch_code': bank_detail.get('branch_code'),
                    'branch_address': bank_detail.get('branch_address'),
                    'account_type': bank_detail.get('account_type'),
                    'currency': bank_detail.get('currency'),
                    'balance': bank_detail.get('balance'),
                    'other_details': bank_detail.get('other_details'),
                    'is_structured_record': True
                }
                results.append(result_dict) 
        
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
    dynamodb_service = DynamoDBService()
    api_keys = dynamodb_service.get_api_keys_by_user(get_user_id(current_user))
    return {"api_keys": api_keys}


@router.post("/user/api-keys", include_in_schema=False)
async def create_user_api_key(
    current_user: UserDB = Depends(get_current_user_required)
):
    """Create a new API key for the current user"""
    dynamodb_service = DynamoDBService()
    api_key = dynamodb_service.create_api_key(get_user_id(current_user))
    return {"api_key": api_key}


@router.put("/user/api-keys/{api_key}/status", include_in_schema=False)
async def update_api_key_status(
    api_key: str,
    status: str,
    current_user: UserDB = Depends(get_current_user_required)
):
    """Update API key status (active/inactive)"""
    dynamodb_service = DynamoDBService()
    # Verify the API key belongs to the current user
    key_data = dynamodb_service.get_api_key(api_key)
    if not key_data or key_data.get('user_id') != get_user_id(current_user):
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Only allow valid status values
    if status not in ['active', 'inactive']:
        raise HTTPException(status_code=400, detail="Invalid status value")
    
    updated_key = dynamodb_service.update_api_key_status(api_key, status)
    return {"api_key": updated_key} 


# endpoint that returns a number presigned urls to the s3 bucket
@router.get("/user/presigned-urls", include_in_schema=False)
async def get_presigned_urls(
    filesUploads: FileUploads,
    current_user: UserDB = Depends(get_current_user_required),
):
    """Get presigned URLs for the current user"""
    s3_service = S3Service()
    presigned_urls = []
    # save the presigned urls to the database
    for file_upload in filesUploads.file_uploads:
        presigned_url = s3_service.generate_presigned_url(get_user_id(current_user))
        presigned_urls.append(presigned_url)
    
    return {"presigned_urls": presigned_urls}


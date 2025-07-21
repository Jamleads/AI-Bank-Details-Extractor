"""
Google Drive integration routes
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.database import get_async_db
from app.models.user import UserDB
from app.services.google_drive_service import GoogleDriveService
from app.utils.auth import get_current_user_required, get_user_id
from app.db.operations import get_raw_extractions
from app.db.header_config import get_header_config
from datetime import datetime
import traceback

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/drive", tags=["drive"], include_in_schema=False)


class DriveExportRequest(BaseModel):
    """Request model for Drive export"""
    file_name: str
    format: str = "csv"
    config_id: Optional[int] = None
    custom_headers: Optional[str] = None


@router.get("/auth")
async def google_drive_auth(
    request: Request,
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Start Google Drive OAuth flow
    
    Args:
        request: Request object
        current_user: Current authenticated user
        
    Returns:
        Redirect to Google OAuth consent screen
    """
    try:
        # Store user ID in session for callback
        request.session['drive_auth_user_id'] = get_user_id(current_user)
        
        # Get auth URL
        auth_url = GoogleDriveService.get_auth_url(request)
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error in Google Drive auth: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to authenticate with Google Drive: {str(e)}")


@router.get("/callback")
async def drive_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Google Drive authorization callback
    
    Args:
        request: FastAPI request
        code: Authorization code
        state: State parameter
        db: Database session
        
    Returns:
        Redirect to main page
    """
    try:
        # Get user ID from session
        user_id = request.session.get('drive_auth_user_id')
        if not user_id:
            logger.error("Missing user ID in session during Drive callback")
            return RedirectResponse(url="/?error=missing_user_id")
        
        # Verify state parameter
        stored_state = request.session.get('drive_auth_state')
        if not stored_state or stored_state != state:
            logger.error(f"Invalid state parameter: got {state}, expected {stored_state}")
            return RedirectResponse(url="/?error=invalid_state")
        
        # Get credentials from code
        try:
            credentials = await GoogleDriveService.get_credentials_from_code(request, code)
        except Exception as auth_error:
            logger.error(f"Error getting credentials from code: {str(auth_error)}")
            return RedirectResponse(url=f"/?error=auth_error&message={str(auth_error)}")
        
        # Store credentials
        try:
            GoogleDriveService.store_credentials(user_id, credentials)
        except Exception as store_error:
            logger.error(f"Error storing credentials: {str(store_error)}")
            return RedirectResponse(url=f"/?error=storage_error&message={str(store_error)}")
        
        # Clear session data
        if 'drive_auth_user_id' in request.session:
            del request.session['drive_auth_user_id']
        if 'drive_auth_state' in request.session:
            del request.session['drive_auth_state']
        
        # Redirect to main page with success message
        return RedirectResponse(url="/?drive_auth=success")
    except Exception as e:
        logger.error(f"Error in drive callback endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return RedirectResponse(url=f"/?error=callback_error&message={str(e)}")


@router.post("/export")
async def export_to_drive(
    request_data: DriveExportRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserDB = Depends(get_current_user_required)
):
    """
    Export data to Google Drive
    
    Args:
        request_data: Export request data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary with file ID and link
    """
    try:
        # Check if user has Google Drive credentials
        credentials = GoogleDriveService.get_stored_credentials(get_user_id(current_user))
        if not credentials:
            raise HTTPException(status_code=401, detail="Google Drive authorization required")
        
        # Get header config if specified
        config_id = request_data.config_id
        header_config = None
        if config_id:
            header_config = await get_header_config(config_id, get_user_id(current_user), db)
            if not header_config:
                raise HTTPException(status_code=404, detail=f"Header configuration with ID {config_id} not found")
        
        # Get raw extractions
        raw_extractions = await get_raw_extractions(get_user_id(current_user), db)
        if not raw_extractions:
            raise HTTPException(status_code=404, detail="No data available to export")
        
        # Prepare data for export
        data = []
        for extraction in raw_extractions:
            # Get source PDF and extraction date
            source_pdf = extraction.get('source_pdf', 'Unknown')
            extraction_date_str = extraction.get('extraction_date', '')
            
            # Handle extraction_date which could be a string or a datetime object
            if isinstance(extraction_date_str, str):
                extraction_date = extraction_date_str
            elif hasattr(extraction_date_str, 'strftime'):
                extraction_date = extraction_date_str.strftime('%Y-%m-%d %H:%M:%S')
            else:
                extraction_date = str(datetime.now())
            
            # Check if raw_data exists and has bank_details
            raw_data = extraction.get('raw_data', {})
            
            if 'bank_details' in raw_data and isinstance(raw_data['bank_details'], list):
                # Add source_pdf and extraction_date to each bank detail
                for bank_detail in raw_data['bank_details']:
                    bank_detail['source_pdf'] = source_pdf
                    bank_detail['extraction_date'] = extraction_date
                    data.append(bank_detail)
            else:
                # If no bank_details field, add the entire raw data as a record
                record = {'source_pdf': source_pdf, 'extraction_date': extraction_date}
                record.update(raw_data)
                data.append(record)
        
        # Apply header mappings if available
        if header_config and 'mappings' in header_config:
            header_mappings = header_config['mappings']
            if "source_pdf" not in header_mappings:
                header_mappings["source_pdf"] = "source_pdf"
            if "extraction_date" not in header_mappings:
                header_mappings["extraction_date"] = "extraction_date"
                
            mapped_records = []
            for record in data:
                mapping_record = {}
                for key, value in record.items():
                    if key in header_mappings:
                        mapping_record[header_mappings[key]] = value
                mapped_records.append(mapping_record)
            
            data = mapped_records
        
        # Export to Google Drive
        custom_headers = request_data.custom_headers
        result = GoogleDriveService.export_to_drive(
            user_id=get_user_id(current_user),
            data=data,
            file_name=request_data.file_name,
            format=request_data.format,
            custom_headers=custom_headers
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting to Google Drive: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to export to Google Drive: {str(e)}")
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
from app.db.operations import get_user_records, get_raw_extractions
from app.db.header_config import get_header_config

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/drive", tags=["drive"])


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
            raise HTTPException(status_code=400, detail="Missing user ID in session")
        
        # Verify state parameter
        stored_state = request.session.get('drive_auth_state')
        if not stored_state or stored_state != state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # Get credentials from code
        credentials = await GoogleDriveService.get_credentials_from_code(request, code)
        
        # Store credentials
        GoogleDriveService.store_credentials(user_id, credentials)
        
        # Redirect to main page
        return RedirectResponse(url="/")
    except Exception as e:
        logger.error(f"Error in drive callback endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        raw_extractions = await get_raw_extractions(get_user_id(current_user), db)
        if not raw_extractions:
            raise HTTPException(status_code=404, detail="No data available to export")
        
        # Prepare data for export
        data = []
        for extraction in raw_extractions:
            if 'raw_data' in extraction and 'bank_details' in extraction['raw_data']:
                data.extend(extraction['raw_data']['bank_details'])
        
        # Export to Google Drive
        result = GoogleDriveService.export_to_drive(
            user_id=get_user_id(current_user),
            data=data,
            file_name=request_data.file_name,
            format=request_data.format,
            custom_headers=request_data.custom_headers
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting to Google Drive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export to Google Drive: {str(e)}")
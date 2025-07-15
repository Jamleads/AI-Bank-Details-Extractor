"""
API routes for Google Drive integration
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import User
from app.services.auth_service import get_current_user_required
from app.services.bank_record_service import get_user_records, get_raw_extractions
from app.services.google_drive_service import GoogleDriveService

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter(prefix="/drive", tags=["drive"])


class DriveExportRequest(BaseModel):
    """Request model for Drive export"""
    file_name: str
    format: str = "csv"
    use_raw: bool = False
    config_id: Optional[int] = None
    custom_headers: Optional[str] = None


@router.get("/auth")
async def drive_auth(
    request: Request,
    current_user: User = Depends(get_current_user_required)
):
    """
    Authorize Google Drive access
    
    Args:
        request: FastAPI request
        current_user: Current authenticated user
        
    Returns:
        Redirect to Google authorization page
    """
    try:
        # Get authorization URL
        auth_url = GoogleDriveService.get_auth_url(request)
        
        # Store user ID in session
        request.session['drive_auth_user_id'] = current_user.id
        
        # Redirect to authorization URL
        return RedirectResponse(auth_url)
    except Exception as e:
        logger.error(f"Error in drive auth endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def drive_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Export bank details to Google Drive
    
    Args:
        request_data: Request body containing export options
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary with file ID and link
    """
    try:
        # Extract parameters from request
        file_name = request_data.file_name
        format = request_data.format
        use_raw = request_data.use_raw
        config_id = request_data.config_id
        custom_headers = request_data.custom_headers
        
        logger.debug(f"Export to Drive endpoint called with file_name={file_name}, format={format}, use_raw={use_raw}, config_id={config_id}")
        
        # Check if user has authorized Google Drive
        credentials = GoogleDriveService.get_stored_credentials(current_user.id)
        if not credentials:
            raise HTTPException(status_code=401, detail="Google Drive authorization required")
        
        # Get header configuration if provided
        header_config = None
        if config_id:
            from app.services.header_config_service import get_header_config
            header_config = await get_header_config(config_id, current_user.id, db)
            if not header_config:
                logger.warning(f"Header configuration with ID {config_id} not found")
                raise HTTPException(status_code=404, detail="Header configuration not found")
            logger.debug(f"Using header configuration: {header_config.name}")
        
        if use_raw:
            # Get raw extractions
            raw_extractions = await get_raw_extractions(current_user.id, db)
            
            if not raw_extractions:
                logger.warning("No raw extractions found for export")
                raise HTTPException(
                    status_code=400, 
                    detail="No raw extractions found. Please process some PDFs first."
                )
            
            logger.debug(f"Found {len(raw_extractions)} raw extractions for export")
            
            # Extract all bank details from raw extractions
            all_bank_details = []
            for extraction in raw_extractions:
                raw_data = extraction['raw_data']
                source_pdf = extraction['source_pdf']
                extraction_date = extraction['extraction_date'].strftime('%Y-%m-%d %H:%M:%S')
                
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
            
            # Export to Google Drive
            result = GoogleDriveService.export_to_drive(
                user_id=current_user.id,
                data=all_bank_details,
                file_name=file_name,
                format=format,
                custom_headers=custom_headers
            )
            
            return result
        else:
            # Get structured records
            records = await get_user_records(current_user.id, db)
            
            if not records:
                logger.warning("No records found for export")
                raise HTTPException(
                    status_code=400, 
                    detail="No records found. Please process some PDFs first."
                )
            
            logger.debug(f"Found {len(records)} records for export")
            
            # Convert records to dict
            records_dict = []
            for record in records:
                records_dict.append({
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
            
            # Apply header mapping if header config is provided
            if header_config:
                from app.services.header_config_service import apply_header_mapping
                records_dict = apply_header_mapping(records_dict, header_config.header_mappings)
            
            # Export to Google Drive
            result = GoogleDriveService.export_to_drive(
                user_id=current_user.id,
                data=records_dict,
                file_name=file_name,
                format=format,
                custom_headers=custom_headers
            )
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in export to Drive endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
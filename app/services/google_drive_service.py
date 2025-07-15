"""
Service for Google Drive integration
"""
import os
import json
import logging
import tempfile
from typing import Optional, Dict, Any, List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from fastapi import HTTPException, Request

from app.core.config import settings
from app.utils.export_utils import generate_csv_file, generate_excel_file, generate_json_file

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Google Drive API scopes - include all scopes used in auth_service.py
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

# Credentials file path
CREDENTIALS_FILE = os.path.join(settings.BASE_DIR, 'credentials.json')


class GoogleDriveService:
    """Service for Google Drive integration"""
    
    @staticmethod
    def get_auth_url(request: Request) -> str:
        """
        Get the authorization URL for Google Drive
        
        Args:
            request: FastAPI request
            
        Returns:
            Authorization URL
        """
        try:
            # Create OAuth 2.0 flow
            flow = Flow.from_client_secrets_file(
                CREDENTIALS_FILE,
                scopes=SCOPES,
                redirect_uri=request.url_for('drive_callback')
            )
            
            # Generate authorization URL
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            # Store state in session
            request.session['drive_auth_state'] = state
            
            return auth_url
        except Exception as e:
            logger.error(f"Error getting Google Drive auth URL: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get Google Drive auth URL: {str(e)}")
    
    @staticmethod
    async def get_credentials_from_code(request: Request, code: str) -> Credentials:
        """
        Get credentials from authorization code
        
        Args:
            request: FastAPI request
            code: Authorization code
            
        Returns:
            Google OAuth credentials
        """
        try:
            # Create OAuth 2.0 flow
            flow = Flow.from_client_secrets_file(
                CREDENTIALS_FILE,
                scopes=SCOPES,
                redirect_uri=request.url_for('drive_callback')
            )
            
            # Get state from session
            state = request.session.get('drive_auth_state')
            if not state:
                raise HTTPException(status_code=400, detail="Missing state parameter")
            
            # Set state in flow
            flow.fetch_token(code=code)
            
            # Return credentials
            return flow.credentials
        except Exception as e:
            logger.error(f"Error getting Google Drive credentials: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get Google Drive credentials: {str(e)}")
    
    @staticmethod
    def store_credentials(user_id: int, credentials: Credentials) -> None:
        """
        Store Google Drive credentials for a user
        
        Args:
            user_id: User ID
            credentials: Google OAuth credentials
        """
        try:
            # Create credentials directory if it doesn't exist
            credentials_dir = os.path.join(settings.BASE_DIR, 'user_credentials')
            os.makedirs(credentials_dir, exist_ok=True)
            
            # Store credentials in a file
            credentials_path = os.path.join(credentials_dir, f'drive_credentials_{user_id}.json')
            
            # Convert credentials to dict and then to JSON
            creds_dict = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            with open(credentials_path, 'w') as f:
                json.dump(creds_dict, f)
            
            logger.debug(f"Stored Google Drive credentials for user {user_id}")
        except Exception as e:
            logger.error(f"Error storing Google Drive credentials: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to store Google Drive credentials: {str(e)}")
    
    @staticmethod
    def get_stored_credentials(user_id: int) -> Optional[Credentials]:
        """
        Get stored Google Drive credentials for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Google OAuth credentials or None if not found
        """
        try:
            # Check if credentials file exists
            credentials_path = os.path.join(settings.BASE_DIR, 'user_credentials', f'drive_credentials_{user_id}.json')
            if not os.path.exists(credentials_path):
                return None
            
            # Load credentials from file
            with open(credentials_path, 'r') as f:
                creds_dict = json.load(f)
            
            # Create credentials object
            credentials = Credentials(
                token=creds_dict['token'],
                refresh_token=creds_dict['refresh_token'],
                token_uri=creds_dict['token_uri'],
                client_id=creds_dict['client_id'],
                client_secret=creds_dict['client_secret'],
                scopes=creds_dict['scopes']
            )
            
            # Check if credentials are valid
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                # Update stored credentials
                GoogleDriveService.store_credentials(user_id, credentials)
            
            return credentials
        except Exception as e:
            logger.error(f"Error getting stored Google Drive credentials: {str(e)}")
            return None
    
    @staticmethod
    def upload_file_to_drive(
        user_id: int, 
        file_path: str, 
        file_name: str, 
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive
        
        Args:
            user_id: User ID
            file_path: Path to the file to upload
            file_name: Name of the file in Google Drive
            mime_type: MIME type of the file
            
        Returns:
            Dictionary with file ID and link
        """
        try:
            # Get credentials
            credentials = GoogleDriveService.get_stored_credentials(user_id)
            if not credentials:
                raise HTTPException(status_code=401, detail="Google Drive authorization required")
            
            # Create Drive API client
            drive_service = build('drive', 'v3', credentials=credentials)
            
            # Create file metadata
            file_metadata = {
                'name': file_name,
                'mimeType': mime_type
            }
            
            # Create media
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            # Upload file
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            logger.debug(f"Uploaded file to Google Drive: {file.get('id')}")
            
            return {
                'file_id': file.get('id'),
                'link': file.get('webViewLink')
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading file to Google Drive: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file to Google Drive: {str(e)}")
    
    @staticmethod
    def export_to_drive(
        user_id: int,
        data: List[Dict[str, Any]],
        file_name: str,
        format: str = 'csv',
        custom_headers: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export data to Google Drive
        
        Args:
            user_id: User ID
            data: Data to export
            file_name: Name of the file in Google Drive
            format: File format (csv or xlsx)
            custom_headers: Optional comma-separated custom headers
            
        Returns:
            Dictionary with file ID and link
        """
        try:
            # Generate file based on format
            if format.lower() == 'csv':
                file_path, _ = generate_csv_file(data, custom_headers)
                mime_type = 'text/csv'
            elif format.lower() == 'json':
                file_path, _ = generate_json_file(data)
                mime_type = 'application/json'
            else:  # xlsx
                file_path, _ = generate_excel_file(data, custom_headers)
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            
            # Upload file to Google Drive
            result = GoogleDriveService.upload_file_to_drive(
                user_id=user_id,
                file_path=file_path,
                file_name=file_name,
                mime_type=mime_type
            )
            
            # Delete temporary file
            os.unlink(file_path)
            
            return result
        except Exception as e:
            logger.error(f"Error exporting to Google Drive: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to export to Google Drive: {str(e)}") 
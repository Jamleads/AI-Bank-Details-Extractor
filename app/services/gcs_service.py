"""
Google Cloud Storage Service for file operations
"""
import os
import uuid
import logging
from typing import Optional, List, BinaryIO, Dict, Any, Tuple
from fastapi import UploadFile
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)

class GCSService:
    """
    Service for Google Cloud Storage file operations
    """
    def __init__(self):
        """Initialize GCS client using ADC"""
        try:
            from google.cloud import storage
            
            # Initialize GCS client using ADC
            if settings.GCP_PROJECT_ID:
                self.client = storage.Client(project=settings.GCP_PROJECT_ID)
            else:
                self.client = storage.Client()
            
            self.bucket_name = settings.GCS_BUCKET
            self.bucket = self.client.bucket(self.bucket_name)
            
            # Initialize signing credentials for presigned URLs
            self._init_signing_credentials()
            
            logger.info(f"GCS service initialized with bucket: {self.bucket_name}")
        except ImportError:
            logger.error("google-cloud-storage not installed. Install with: pip install google-cloud-storage")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {str(e)}")
            raise
    
    def _init_signing_credentials(self):
        """Initialize signing credentials using service account impersonation"""
        try:
            from google.auth import default, impersonated_credentials
            
            # Get default credentials and project
            source_credentials, project = default()
            
            # Create impersonated credentials for the app service account
            target_service_account = f"ai-bank-extractor-sa@{project}.iam.gserviceaccount.com"
            
            self.signing_credentials = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=target_service_account,
                target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
                delegates=[]
            )
            
            self.project_id = project
            logger.info(f"Impersonated signing credentials initialized for: {target_service_account}")
            
        except Exception as e:
            logger.warning(f"Could not initialize impersonated credentials: {e}. Signed URLs will not work.")
            self.signing_credentials = None
    
    def _create_signed_url_v4(self, object_name: str, method: str, expiration: int = 3600, content_type: str = None) -> Optional[str]:
        """
        Create a signed URL using impersonated credentials
        """
        try:
            if not self.signing_credentials:
                logger.error("Signing credentials not available")
                return None
            
            from datetime import datetime, timedelta
            
            blob = self.bucket.blob(object_name)
            
            # Generate signed URL using the Google Cloud Storage library
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.now() + timedelta(seconds=expiration),
                method=method,
                content_type=content_type,
                credentials=self.signing_credentials
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Error creating signed URL with impersonated credentials: {str(e)}")
            return None
    
    async def upload_file(self, file: UploadFile, prefix: str = "", user_id: str = None) -> Optional[str]:
        """
        Upload a file to GCS
        
        Args:
            file: The file to upload
            prefix: The GCS object key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            The GCS object name of the uploaded file or None if upload failed
        """
        try:
            # Create GCS object name with prefix and original filename
            object_name = self._build_key(prefix, file.filename, user_id)
            
            # Read file content
            contents = await file.read()
            
            # Create blob and upload
            blob = self.bucket.blob(object_name)
            blob.upload_from_string(
                contents,
                content_type=file.content_type
            )
            
            await file.seek(0)  # Reset file pointer
            logger.info(f"Successfully uploaded file to GCS: {object_name}")
            return object_name
        except Exception as e:
            logger.error(f"Error uploading file to GCS: {str(e)}")
            return None
    
    def upload_data(self, data: bytes, filename: str, content_type: str, 
                   prefix: str = "", user_id: str = None) -> Optional[str]:
        """
        Upload data directly to GCS
        
        Args:
            data: The binary data to upload
            filename: The target filename
            content_type: MIME type of the data
            prefix: The GCS object key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            The GCS object name of the uploaded data or None if upload failed
        """
        try:
            # Create GCS object name with prefix and filename
            object_name = self._build_key(prefix, filename, user_id)
            
            # Create blob and upload
            blob = self.bucket.blob(object_name)
            blob.upload_from_string(
                data,
                content_type=content_type
            )
            
            logger.info(f"Successfully uploaded data to GCS: {object_name}")
            return object_name
        except Exception as e:
            logger.error(f"Error uploading data to GCS: {str(e)}")
            return None
    
    def download_file(self, object_name: str) -> Optional[Tuple[bytes, str]]:
        """
        Download a file from GCS
        
        Args:
            object_name: The GCS object name of the file to download
            
        Returns:
            Tuple of (file_content, content_type) or None if download failed
        """
        try:
            blob = self.bucket.blob(object_name)
            
            # Check if blob exists
            if not blob.exists():
                logger.error(f"File not found in GCS: {object_name}")
                return None
            
            # Download the file content
            content = blob.download_as_bytes()
            content_type = blob.content_type or 'application/octet-stream'
            
            return (content, content_type)
        except Exception as e:
            logger.error(f"Error downloading file from GCS: {str(e)}")
            return None
    
    def list_files(self, prefix: str = "", user_id: str = None) -> List[Dict[str, Any]]:
        """
        List files in GCS bucket with given prefix
        
        Args:
            prefix: The GCS object key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            List of file objects with keys and metadata
        """
        try:
            # Build the full prefix if user_id is provided
            if user_id:
                full_prefix = f"{prefix}/{user_id}/" if prefix else f"{user_id}/"
            else:
                full_prefix = f"{prefix}/" if prefix else ""
            
            # List objects with the prefix
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=full_prefix
            )
            
            # Extract and return file information
            files = []
            for blob in blobs:
                # Get just the filename from the full object name
                object_name = blob.name
                filename = object_name.split('/')[-1] if '/' in object_name else object_name
                
                files.append({
                    'key': blob.name,
                    'filename': filename,
                    'size': blob.size or 0,
                    'last_modified': blob.updated.isoformat() if blob.updated else datetime.now().isoformat(),
                })
            
            return files
        except Exception as e:
            logger.error(f"Error listing files in GCS: {str(e)}")
            return []
    
    def delete_file(self, object_name: str) -> bool:
        """
        Delete a file from GCS
        
        Args:
            object_name: The GCS object name of the file to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            blob = self.bucket.blob(object_name)
            blob.delete()
            logger.info(f"Successfully deleted file from GCS: {object_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file from GCS: {str(e)}")
            return False
    
    def generate_presigned_url(self, user_id: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a signed URL for uploading a file (legacy method)
        
        Args:
            user_id: The user ID to include in the object name
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Signed URL or None if generation failed
        """
        try:
            # Generate a unique object name using UUID
            object_name = f"{user_id}/{uuid.uuid4()}"
            
            # Use IAM-based signing
            return self._create_signed_url_v4(object_name, "PUT", expiration)
            
        except Exception as e:
            logger.error(f"Error generating signed upload URL: {str(e)}")
            return None
    
    def generate_presigned_url_with_metadata(
        self, 
        user_id: str, 
        filename: str,
        content_type: str,
        expiration: int = 3600
    ) -> Optional[Dict[str, str]]:
        """
        Generate a signed URL for uploading a specific file with metadata
        
        Args:
            user_id: The user ID to include in the object name
            filename: Original filename
            content_type: MIME type of the file
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Dict with signed_url, object_name, and metadata or None if generation failed
        """
        try:
            # Generate file extension from filename
            file_extension = os.path.splitext(filename)[1] if '.' in filename else ''
            
            # Generate unique object name with extension
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            object_name = f"uploads/{user_id}/{unique_filename}"
            
            # Use IAM-based signing with content type
            url = self._create_signed_url_v4(object_name, "PUT", expiration, content_type)
            
            if not url:
                return None
            
            return {
                'presigned_url': url,  # Keep same key name for compatibility
                'file_key': object_name,  # Keep same key name for compatibility
                'content_type': content_type,
                'original_filename': filename
            }
        except Exception as e:
            logger.error(f"Error generating signed upload URL with metadata: {str(e)}")
            return None
    
    def check_file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in GCS
        
        Args:
            object_name: The GCS object name of the file to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            blob = self.bucket.blob(object_name)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking if file exists in GCS: {str(e)}")
            return False
    
    def _build_key(self, prefix: str, filename: str, user_id: str = None) -> str:
        """
        Build the GCS object name with the given prefix, user_id, and filename
        
        Args:
            prefix: The GCS object key prefix (folder)
            filename: The filename
            user_id: User ID to include in prefix
            
        Returns:
            The complete GCS object name
        """
        if user_id:
            if prefix:
                return f"{prefix}/{user_id}/{filename}"
            return f"{user_id}/{filename}"
        
        if prefix:
            return f"{prefix}/{filename}"
        return filename

    def generate_download_url(self, object_name: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a signed URL for downloading a file
        
        Args:
            object_name: The GCS object name of the file
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Signed download URL or None if generation failed
        """
        try:
            # Use IAM-based signing for download
            return self._create_signed_url_v4(object_name, "GET", expiration)
            
        except Exception as e:
            logger.error(f"Error generating signed download URL: {str(e)}")
            return None


# Create singleton instance
try:
    gcs_service = GCSService() if settings.GCS_BUCKET else None
except Exception as e:
    logger.error(f"Failed to initialize GCS service: {str(e)}")
    gcs_service = None

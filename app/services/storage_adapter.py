"""
Storage adapter for switching between S3 and Google Cloud Storage
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from fastapi import UploadFile
from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageAdapter:
    """Storage adapter for switching between S3 and GCS"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StorageAdapter, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the appropriate storage backend"""
        self.cloud = settings.CLOUD
        self.use_cloud_storage = settings.USE_S3_STORAGE or settings.USE_GCS_STORAGE
        
        if not self.use_cloud_storage:
            logger.info("Cloud storage disabled - using local file storage")
            self._storage_provider = None
            return
        
        if self.cloud == "GCP" and settings.USE_GCS_STORAGE:
            try:
                from app.services.gcs_service import gcs_service
                self._storage_provider = gcs_service
                self.storage_type = "gcs"
                logger.info("Storage adapter initialized with Google Cloud Storage")
            except Exception as e:
                logger.error(f"Failed to initialize GCS: {str(e)}")
                logger.info("Falling back to S3")
                self._initialize_s3()
        elif self.cloud == "AWS" and settings.USE_S3_STORAGE:
            self._initialize_s3()
        elif settings.USE_GCS_STORAGE:
            # Fallback to GCS
            try:
                from app.services.gcs_service import gcs_service
                self._storage_provider = gcs_service
                self.storage_type = "gcs"
                logger.info("Storage adapter initialized with GCS (fallback)")
            except Exception as e:
                logger.error(f"Failed to initialize GCS fallback: {str(e)}")
                self._initialize_s3()
        elif settings.USE_S3_STORAGE:
            # Fallback to S3
            self._initialize_s3()
        else:
            logger.info("No cloud storage configured - using local file storage")
            self._storage_provider = None
            
    def _initialize_s3(self):
        """Initialize S3 storage"""
        try:
            from app.services.s3_service import s3_service
            self._storage_provider = s3_service
            self.storage_type = "s3"
            logger.info("Storage adapter initialized with AWS S3")
        except Exception as e:
            logger.error(f"Failed to initialize S3: {str(e)}")
            self._storage_provider = None

    async def upload_file(self, file: UploadFile, prefix: str = "", user_id: str = None) -> Optional[str]:
        """
        Upload a file to cloud storage
        
        Args:
            file: The file to upload
            prefix: The storage key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            The storage key/object name of the uploaded file or None if upload failed
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return None
        
        return await self._storage_provider.upload_file(file, prefix, user_id)

    def upload_data(self, data: bytes, filename: str, content_type: str, 
                   prefix: str = "", user_id: str = None) -> Optional[str]:
        """
        Upload data directly to cloud storage
        
        Args:
            data: The binary data to upload
            filename: The target filename
            content_type: MIME type of the data
            prefix: The storage key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            The storage key/object name of the uploaded data or None if upload failed
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return None
        
        return self._storage_provider.upload_data(data, filename, content_type, prefix, user_id)

    def download_file(self, file_key: str) -> Optional[Tuple[bytes, str]]:
        """
        Download a file from cloud storage
        
        Args:
            file_key: The storage key/object name of the file to download
            
        Returns:
            Tuple of (file_content, content_type) or None if download failed
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return None
        
        return self._storage_provider.download_file(file_key)

    def list_files(self, prefix: str = "", user_id: str = None) -> List[Dict[str, Any]]:
        """
        List files in cloud storage bucket with given prefix
        
        Args:
            prefix: The storage key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            List of file objects with keys and metadata
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return []
        
        return self._storage_provider.list_files(prefix, user_id)

    def delete_file(self, file_key: str) -> bool:
        """
        Delete a file from cloud storage
        
        Args:
            file_key: The storage key/object name of the file to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return False
        
        return self._storage_provider.delete_file(file_key)

    def generate_presigned_url(self, user_id: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned/signed URL for uploading a file (legacy method)
        
        Args:
            user_id: The user ID to include in the file key
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned/signed URL or None if generation failed
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return None
        
        return self._storage_provider.generate_presigned_url(user_id, expiration)

    def generate_presigned_url_with_metadata(
        self, 
        user_id: str, 
        filename: str,
        content_type: str,
        expiration: int = 3600
    ) -> Optional[Dict[str, str]]:
        """
        Generate a presigned/signed URL for uploading a specific file with metadata
        
        Args:
            user_id: The user ID to include in the file key
            filename: Original filename
            content_type: MIME type of the file
            expiration: URL expiration time in seconds
            
        Returns:
            Dict with presigned_url, file_key, and metadata or None if generation failed
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return None
        
        return self._storage_provider.generate_presigned_url_with_metadata(
            user_id, filename, content_type, expiration
        )

    def check_file_exists(self, file_key: str) -> bool:
        """
        Check if a file exists in cloud storage
        
        Args:
            file_key: The storage key/object name of the file to check
            
        Returns:
            True if file exists, False otherwise
        """
        if not self._storage_provider:
            logger.warning("No storage provider configured")
            return False
        
        return self._storage_provider.check_file_exists(file_key)

    def get_storage_type(self) -> str:
        """
        Get the current storage type
        
        Returns:
            's3', 'gcs', or 'local'
        """
        if not self._storage_provider:
            return 'local'
        
        return getattr(self, 'storage_type', 'unknown')

    def is_cloud_storage_enabled(self) -> bool:
        """
        Check if cloud storage is enabled and configured
        
        Returns:
            True if cloud storage is available, False otherwise
        """
        return self._storage_provider is not None

    def get_bucket_name(self) -> Optional[str]:
        """
        Get the current bucket/container name
        
        Returns:
            Bucket name or None if not configured
        """
        if not self._storage_provider:
            return None
        
        if hasattr(self._storage_provider, 'bucket_name'):
            return self._storage_provider.bucket_name
        elif hasattr(self._storage_provider, 'bucket'):
            return self._storage_provider.bucket.name
        else:
            return None

# Create a singleton instance
storage = StorageAdapter()

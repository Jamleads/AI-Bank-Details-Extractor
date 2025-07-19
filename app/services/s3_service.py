"""
S3 Service for file operations
"""
import os
import boto3
import logging
from botocore.exceptions import ClientError
from typing import Optional, List, BinaryIO, Dict, Any, Tuple
from fastapi import UploadFile
from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    """
    Service for S3 file operations
    """
    def __init__(self):
        """Initialize S3 client"""
        self.bucket_name = settings.S3_BUCKET
        self.region = settings.AWS_REGION
        self.s3 = boto3.client('s3', region_name=self.region)
    
    async def upload_file(self, file: UploadFile, prefix: str = "", user_id: str = None) -> Optional[str]:
        """
        Upload a file to S3
        
        Args:
            file: The file to upload
            prefix: The S3 key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            The S3 key of the uploaded file or None if upload failed
        """
        try:
            # Create S3 key with prefix and original filename
            file_key = self._build_key(prefix, file.filename, user_id)
            
            # Read file content
            contents = await file.read()
            
            # Upload to S3
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=contents,
                ContentType=file.content_type
            )
            
            await file.seek(0)  # Reset file pointer
            logger.info(f"Successfully uploaded file to S3: {file_key}")
            return file_key
        except Exception as e:
            logger.error(f"Error uploading file to S3: {str(e)}")
            return None
    
    def upload_data(self, data: bytes, filename: str, content_type: str, 
                   prefix: str = "", user_id: str = None) -> Optional[str]:
        """
        Upload data directly to S3
        
        Args:
            data: The binary data to upload
            filename: The target filename
            content_type: MIME type of the data
            prefix: The S3 key prefix (folder)
            user_id: User ID to include in prefix
            
        Returns:
            The S3 key of the uploaded data or None if upload failed
        """
        try:
            # Create S3 key with prefix and filename
            file_key = self._build_key(prefix, filename, user_id)
            
            # Upload to S3
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=data,
                ContentType=content_type
            )
            
            logger.info(f"Successfully uploaded data to S3: {file_key}")
            return file_key
        except Exception as e:
            logger.error(f"Error uploading data to S3: {str(e)}")
            return None
    
    def download_file(self, file_key: str) -> Optional[Tuple[bytes, str]]:
        """
        Download a file from S3
        
        Args:
            file_key: The S3 key of the file to download
            
        Returns:
            Tuple of (file_content, content_type) or None if download failed
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=file_key)
            return (response['Body'].read(), response.get('ContentType', 'application/octet-stream'))
        except Exception as e:
            logger.error(f"Error downloading file from S3: {str(e)}")
            return None
    
    def list_files(self, prefix: str = "", user_id: str = None) -> List[Dict[str, Any]]:
        """
        List files in S3 bucket with given prefix
        
        Args:
            prefix: The S3 key prefix (folder)
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
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=full_prefix
            )
            
            # Extract and return file information
            files = []
            if 'Contents' in response:
                for item in response['Contents']:
                    # Get just the filename from the full key
                    key = item['Key']
                    filename = key.split('/')[-1] if '/' in key else key
                    
                    files.append({
                        'key': item['Key'],
                        'filename': filename,
                        'size': item['Size'],
                        'last_modified': item['LastModified'].isoformat(),
                    })
            
            return files
        except Exception as e:
            logger.error(f"Error listing files in S3: {str(e)}")
            return []
    
    def delete_file(self, file_key: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            file_key: The S3 key of the file to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=file_key)
            logger.info(f"Successfully deleted file from S3: {file_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            return False
    
    def generate_presigned_url(self, file_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for a file
        
        Args:
            file_key: The S3 key of the file
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL or None if generation failed
        """
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return None
    
    def check_file_exists(self, file_key: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            file_key: The S3 key of the file to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except ClientError:
            return False
        except Exception as e:
            logger.error(f"Error checking if file exists in S3: {str(e)}")
            return False
    
    def _build_key(self, prefix: str, filename: str, user_id: str = None) -> str:
        """
        Build the S3 key with the given prefix, user_id, and filename
        
        Args:
            prefix: The S3 key prefix (folder)
            filename: The filename
            user_id: User ID to include in prefix
            
        Returns:
            The complete S3 key
        """
        if user_id:
            if prefix:
                return f"{prefix}/{user_id}/{filename}"
            return f"{user_id}/{filename}"
        
        if prefix:
            return f"{prefix}/{filename}"
        return filename


# Create singleton instance
s3_service = S3Service() 
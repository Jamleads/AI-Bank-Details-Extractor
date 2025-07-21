"""
Ads Service for managing advertisements
"""
import os
import uuid
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import UploadFile
from datetime import datetime
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)

class AdsService:
    """
    Service for managing advertisements
    """
    def __init__(self, s3_service: S3Service):
        """Initialize Ads service"""
        self.s3_service = s3_service
        self.ads_prefix = "ads"  # Prefix for ads in S3
    
    async def upload_ad(self, image: UploadFile, ad_text: str) -> Optional[Dict[str, Any]]:
        """
        Upload an advertisement image with text to S3
        
        Args:
            image: The ad image file
            ad_text: The advertisement text
            
        Returns:
            Dictionary with ad details or None if upload failed
        """
        try:
            # Generate a unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            file_extension = os.path.splitext(image.filename)[1]
            new_filename = f"ad_{timestamp}{file_extension}"
            
            # Upload to S3 with metadata
            metadata = {
                "ad_text": ad_text,
                "uploaded_at": timestamp
            }
            
            # Read file content
            contents = await image.read()
            
            # Upload to S3 with metadata
            file_key = self.s3_service._build_key(self.ads_prefix, new_filename)
            
            self.s3_service.s3.put_object(
                Bucket=self.s3_service.bucket_name,
                Key=file_key,
                Body=contents,
                ContentType=image.content_type,
                Metadata=metadata
            )
            
            await image.seek(0)  # Reset file pointer
            logger.info(f"Successfully uploaded ad to S3: {file_key}")
            
            return {
                "key": file_key,
                "filename": new_filename,
                "ad_text": ad_text,
                "uploaded_at": timestamp
            }
        except Exception as e:
            logger.error(f"Error uploading ad to S3: {str(e)}")
            return None
    
    def get_latest_ad(self, expiration: int = 43200) -> Optional[Dict[str, Any]]:
        """
        Get the latest advertisement with a presigned URL
        
        Args:
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Dictionary with ad details and presigned URL or None if no ads found
        """
        try:
            # List all ads
            ads = self.s3_service.list_files(prefix=self.ads_prefix)
            
            if not ads:
                logger.info("No ads found in S3")
                return None
            
            # Sort by last_modified (most recent first)
            ads.sort(key=lambda x: x['last_modified'], reverse=True)
            latest_ad = ads[0]
            
            # Get the ad metadata
            response = self.s3_service.s3.head_object(
                Bucket=self.s3_service.bucket_name,
                Key=latest_ad['key']
            )
            
            metadata = response.get('Metadata', {})
            ad_text = metadata.get('ad_text', '')
            
            # Generate a presigned URL for the image
            presigned_url = self.s3_service.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.s3_service.bucket_name,
                    'Key': latest_ad['key']
                },
                ExpiresIn=expiration
            )
            
            return {
                "key": latest_ad['key'],
                "filename": latest_ad['filename'],
                "ad_text": ad_text,
                "uploaded_at": metadata.get('uploaded_at', ''),
                "url": presigned_url
            }
        except Exception as e:
            logger.error(f"Error getting latest ad from S3: {str(e)}")
            return None


# Create singleton instance using the existing S3 service
from app.services.s3_service import s3_service
ads_service = AdsService(s3_service) 
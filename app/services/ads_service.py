"""
Ads Service for managing advertisements
"""
import os
import uuid
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import UploadFile
from datetime import datetime
from app.services.storage_adapter import storage

logger = logging.getLogger(__name__)

class AdsService:
    """
    Service for managing advertisements
    """
    def __init__(self, storage_adapter):
        """Initialize Ads service"""
        self.storage = storage_adapter
        self.ads_prefix = "ads"  # Prefix for ads in cloud storage
    

    async def upload_ad(self, image: UploadFile, link: str, ad_text: str = "") -> Optional[Dict[str, Any]]:
        """
        Upload a banner-style advertisement with image, link, and optional text to cloud storage
        
        Args:
            image: The ad image file
            link: The URL to redirect when banner is clicked
            ad_text: Optional text to display below the banner (default: empty)
            
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
                "link": link,
                "ad_text": ad_text,
                "uploaded_at": timestamp
            }
            
            # Read file content
            contents = await image.read()
            
            # Upload to cloud storage using the adapter
            file_key = self.storage.upload_data(
                data=contents,
                filename=new_filename,
                content_type=image.content_type or 'application/octet-stream',
                prefix=self.ads_prefix
            )
            
            if not file_key:
                logger.error("Failed to upload ad to cloud storage")
                return None
            
            await image.seek(0)  # Reset file pointer
            logger.info(f"Successfully uploaded ad to cloud storage: {file_key}")
            
            return {
                "key": file_key,
                "filename": new_filename,
                "link": link,
                "ad_text": ad_text,
                "uploaded_at": timestamp
            }
        except Exception as e:
            logger.error(f"Error uploading ad to cloud storage: {str(e)}")
            return None
    
    async def get_latest_ad(self, expiration: int = 43200) -> Optional[Dict[str, Any]]:
        """
        Get the latest advertisement with a presigned URL
        
        Args:
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Dictionary with ad details and presigned URL or None if no ads found
        """
        try:
            # Check if cloud storage is properly configured
            if not self.storage.is_cloud_storage_enabled():
                logger.warning("Cloud storage not configured, cannot retrieve ads")
                return None
            
            logger.debug("Listing ads from cloud storage...")
            # List all ads
            ads = self.storage.list_files(prefix=self.ads_prefix)
            
            logger.debug(f"Found {len(ads) if ads else 0} ads in cloud storage")
            if not ads:
                logger.info("No ads found in cloud storage")
                return None
            
            # Sort by last_modified (most recent first)
            ads.sort(key=lambda x: x['last_modified'], reverse=True)
            latest_ad = ads[0]
            
            logger.debug(f"Latest ad key: {latest_ad['key']}")
            
            # Note: Metadata functionality is not available through the storage adapter
            # This is a simplified version that doesn't include ad text and link metadata
            # TODO: Consider storing metadata separately or extending the storage adapter interface
            
            # Generate a download URL for the image using the storage adapter
            if hasattr(self.storage._storage_provider, 'generate_download_url'):
                # For GCS
                presigned_url = self.storage._storage_provider.generate_download_url(
                    latest_ad['key'], expiration
                )
            else:
                # For S3 - fallback to direct S3 service if needed
                presigned_url = self.storage._storage_provider.s3.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.storage._storage_provider.bucket_name,
                        'Key': latest_ad['key']
                    },
                    ExpiresIn=expiration
                )
            
            logger.debug(f"Generated presigned URL: {presigned_url[:100]}...")
            return {
                "key": latest_ad['key'],
                "filename": latest_ad['filename'],
                "link": "",  # Metadata not available through storage adapter
                "ad_text": "",  # Metadata not available through storage adapter
                "uploaded_at": latest_ad.get('last_modified', ''),
                "url": presigned_url
            }
        except Exception as e:
            logger.error(f"Error getting latest ad from cloud storage: {str(e)}")
            return None


# Create singleton instance using the storage adapter
ads_service = AdsService(storage) 
from typing import List, Optional
from pydantic import BaseModel


class FileUpload(BaseModel):
    """Model for file upload"""
    file_id: str
    file_name: str


class FileUploads(BaseModel):
    """Model for file uploads"""
    file_uploads: List[FileUpload]


class FileUploadRequest(BaseModel):
    """Model for requesting presigned URL"""
    filename: str
    content_type: str
    size: int


class S3FileReference(BaseModel):
    """Model for referencing uploaded S3 files"""
    file_id: str
    file_key: str  # S3 key
    filename: str
    content_type: str
    size: Optional[int] = None


class ExtractRequest(BaseModel):
    """Model for extract endpoint request"""
    files: List[S3FileReference]
    header_config_id: Optional[str] = None


class PresignedUrlResponse(BaseModel):
    """Model for presigned URL response"""
    file_id: str
    filename: str
    presigned_url: str
    file_key: str
    content_type: str


class ProcessFileRequest(BaseModel):
    """Model for processing a single file"""
    file_ref: S3FileReference
    header_config_id: Optional[str] = None


class PresignedUrlsResponse(BaseModel):
    """Model for presigned URLs response"""
    presigned_urls: List[PresignedUrlResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "presigned_urls": [
                    {
                        "file_id": "12345678-1234-1234-1234-123456789012",
                        "filename": "bank_statement.pdf",
                        "presigned_url": "https://storage.googleapis.com/bucket/signed-url",
                        "file_key": "user123/file456",
                        "content_type": "application/pdf"
                    }
                ]
            }
        }

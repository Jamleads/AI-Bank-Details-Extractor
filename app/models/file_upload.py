from typing import List
from pydantic import BaseModel


class FileUpload(BaseModel):
    """Model for file upload"""
    file_id: str
    file_name: str


class FileUploads(BaseModel):
    """Model for file uploads"""
    file_uploads: List[FileUpload]

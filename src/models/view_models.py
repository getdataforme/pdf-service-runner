"""
Request models for PDF viewing endpoints
"""

from pydantic import BaseModel
from typing import Optional


class PDFViewRequestModel(BaseModel):
    """Request model for viewing PDF documents."""
    file_path: str
    bucket_name: Optional[str] = "courts-bucket"
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "orange/case_123/document.pdf",
                "bucket_name": "courts-bucket"
            }
        }

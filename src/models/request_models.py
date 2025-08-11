"""
Request Models for PDF Extraction API

Defines the data models for API requests and responses.
"""

from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Annotated, Optional, Union


class PDFRequestModel(BaseModel):
    """
    Model for PDF extraction request.
    
    Attributes:
        county_name: Name of the county to process
        document_type: Type of documents to extract from
        date_to: End date for document filtering
        date_from: Start date for document filtering (optional)
    """
    county_name: Annotated[str, Field(min_length=1, description="County name (e.g., 'orange', 'los_angeles')")]
    document_type: Annotated[str, Field(min_length=1, description="Document type (e.g., 'complaint', 'motion')")]
    date_to: Annotated[date, Field(description="End date for document filtering (YYYY-MM-DD)")]
    date_from: Optional[Annotated[date, Field(description="Start date for document filtering (YYYY-MM-DD)")]] = None

    @validator('county_name')
    def validate_county_name(cls, v):
        """Validate and normalize county name."""
        return v.lower().strip().replace(' ', '_')
    
    @validator('document_type')
    def validate_document_type(cls, v):
        """Validate and normalize document type."""
        return v.lower().strip()
    
    @validator('date_from')
    def validate_date_range(cls, v, values):
        """Ensure date_from is before date_to if provided."""
        if v and 'date_to' in values and v > values['date_to']:
            raise ValueError('date_from must be before date_to')
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "county_name": "orange",
                "document_type": "complaint",
                "date_to": "2024-12-31",
                "date_from": "2024-01-01"
            }
        }
    }


class IndividualPDFRequestModel(BaseModel):
    """
    Model for individual document PDF extraction request.
    
    Attributes:
        case_id: PostgreSQL case ID (for reference)
        mongo_id: MongoDB case ObjectId (for database updates)
        doc_path: GCS path to the specific document
        document_description: Human-readable description of the document
    """
    case_id: Annotated[Union[str, int], Field(description="PostgreSQL case ID (string or integer)")]
    mongo_id: Annotated[Optional[str], Field(description="MongoDB ObjectId (24-character hex string)")] = None
    doc_path: Annotated[str, Field(min_length=1, description="GCS path to the document")]
    document_description: Annotated[str, Field(min_length=1, description="Description of the document")]

    @validator('case_id')
    def validate_case_id(cls, v):
        """Convert case_id to string."""
        return str(v)

    @validator('mongo_id')
    def validate_mongo_id(cls, v):
        """Validate MongoDB ObjectId format if provided."""
        if v is None:
            return v
        if len(v) != 24:
            raise ValueError('mongo_id must be a 24-character hex string')
        try:
            # Try to create ObjectId to validate format
            from bson import ObjectId
            ObjectId(v)
            return v
        except Exception:
            raise ValueError('mongo_id must be a valid ObjectId hex string')

    @validator('doc_path')
    def validate_doc_path(cls, v):
        """Validate that doc_path looks like a GCS path."""
        if not v.strip():
            raise ValueError('doc_path cannot be empty')
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "case_id": "507f1f77bcf86cd799439011",
                "doc_path": "orangecounty/2023/complaints/complaint_12345.pdf",
                "document_description": "Initial Complaint Document"
            }
        }
    }


class JobStatusResponse(BaseModel):
    """
    Model for job status response.
    
    Attributes:
        job_id: Unique identifier for the job
        status: Current status of the job
        message: Human-readable status message
        county_name: County being processed
        document_type: Document type being processed
        result: Results of the extraction (if completed)
        error: Error message (if failed)
    """
    job_id: str
    status: str  # started, processing, completed, failed
    message: str
    county_name: str
    document_type: str
    date_to: str
    date_from: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
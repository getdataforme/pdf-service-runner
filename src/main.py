"""
PDF Extraction Service API

FastAPI-based service for orchestrating PDF download and extraction workflows.
Provides endpoints for starting extraction jobs, checking status, and retrieving results.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
from src.models.request_models import PDFRequestModel, IndividualPDFRequestModel
from src.models.view_models import PDFViewRequestModel
from src.service.pdf_service import PDFService
from src.service.pdf_viewer_service import PDFViewerService
from src.utils.logger import setup_logger
from src.utils.env_loader import load_root_env  # Load environment from root .env
import asyncio
import uuid
from typing import Dict
import sys
sys.path.append('.')

# Initialize FastAPI app
app = FastAPI(
    title="PDF Extraction Service", 
    version="1.0.0",
    description="Service for extracting data from court PDF documents"
)

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logger
logger = setup_logger()

# Initialize PDF viewer service
pdf_viewer_service = PDFViewerService()

# In-memory store for tracking job status
job_status: Dict[str, dict] = {}


@app.get("/")
async def root():
    """Root endpoint providing service information."""
    return {
        "message": "PDF Extraction Service is running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "extract": "/extract",
            "extract_individual": "/extract-individual",
            "view_pdf": "/view-pdf",
            "status": "/status/{job_id}",
            "jobs": "/jobs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "pdf-extraction"}


@app.post("/extract")
async def extract_pdfs(request: PDFRequestModel, background_tasks: BackgroundTasks):
    """
    Start PDF extraction process for a given county and document type.
    
    Args:
        request: PDF extraction request parameters
        background_tasks: FastAPI background tasks handler
        
    Returns:
        Job information including job_id for status tracking
    """
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    job_status[job_id] = {
        "job_id": job_id,
        "status": "started",
        "county_name": request.county_name,
        "document_type": request.document_type,
        "date_to": str(request.date_to),
        "date_from": str(request.date_from) if request.date_from else None,
        "message": "PDF extraction job started",
        "created_at": str(uuid.uuid4())  # Use timestamp in production
    }
    
    # Add background task
    background_tasks.add_task(
        run_pdf_extraction,
        job_id,
        request.county_name,
        request.document_type,
        str(request.date_to),
        str(request.date_from) if request.date_from else None
    )
    
    logger.info(f"Started PDF extraction job {job_id} for {request.county_name}")
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": f"PDF extraction started for {request.county_name}",
        "county_name": request.county_name,
        "document_type": request.document_type
    }


@app.post("/extract-individual")
async def extract_individual_pdf(request: IndividualPDFRequestModel):
    """
    Extract data from a single PDF document.
    
    Args:
        request: Individual PDF extraction request parameters
        
    Returns:
        Extraction results for the individual document
    """
    try:
        logger.info(f"Starting individual PDF extraction for case {request.case_id}")
        
        # Initialize extractor and extract individual document
        from src.service.individual_pdf_service import IndividualPDFService
        
        individual_service = IndividualPDFService()
        result = await individual_service.extract_individual_document(
            str(request.case_id),
            request.mongo_id,  # Pass the MongoDB ObjectId for database updates
            request.doc_path,
            request.document_description
        )
        
        logger.info(f"Individual PDF extraction completed for case {request.case_id}")
        
        return {
            "success": True,
            "message": f"Successfully extracted data from {request.document_description}",
            "case_id": request.case_id,
            "doc_path": request.doc_path,
            "extracted_data": result
        }
        
    except Exception as e:
        logger.error(f"Individual PDF extraction failed for case {request.case_id}: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to extract data from {request.document_description}",
            "case_id": request.case_id,
            "doc_path": request.doc_path,
            "error": str(e)
        }


@app.post("/view-pdf", response_class=HTMLResponse)
async def view_pdf(request: PDFViewRequestModel):
    """
    Serve PDF viewer with the requested PDF document.
    
    Args:
        request: PDF view request parameters
        
    Returns:
        HTML response containing embedded PDF viewer
    """
    try:
        logger.info(f"PDF view request for: {request.file_path}")
        
        # Use the PDF viewer service to generate the HTML response
        html_response = await pdf_viewer_service.view_pdf(
            file_path=request.file_path,
            bucket_name=request.bucket_name
        )
        
        return html_response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in PDF viewer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/view-pdf/{file_path:path}", response_class=HTMLResponse)
async def view_pdf_get(file_path: str, bucket_name: str = "courts-bucket"):
    """
    Serve PDF viewer with the requested PDF document (GET endpoint).
    
    Args:
        file_path: Path to the PDF file in GCS
        bucket_name: GCS bucket name (optional, defaults to courts-bucket)
        
    Returns:
        HTML response containing embedded PDF viewer
    """
    try:
        logger.info(f"PDF view GET request for: {file_path}")
        
        # Use the PDF viewer service to generate the HTML response
        html_response = await pdf_viewer_service.view_pdf(
            file_path=file_path,
            bucket_name=bucket_name
        )
        
        return html_response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in PDF viewer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of a PDF extraction job.
    
    Args:
        job_id: Unique identifier for the job
        
    Returns:
        Current job status and results
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]


@app.get("/jobs")
async def list_jobs():
    """
    List all jobs and their current status.
    
    Returns:
        Dictionary of all jobs with their status information
    """
    return {"jobs": job_status, "total_jobs": len(job_status)}


async def run_pdf_extraction(job_id: str, county_name: str, document_type: str, 
                           date_to: str, date_from: str | None = None):
    """
    Background task to run PDF extraction workflow.
    
    Args:
        job_id: Unique identifier for the job
        county_name: Name of the county to process
        document_type: Type of documents to process
        date_to: End date for document filtering
        date_from: Start date for document filtering (optional)
    """
    try:
        # Update status to processing
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "Downloading and processing PDFs..."
        
        # Initialize PDF service
        pdf_service = PDFService(county_name, document_type, date_to, date_from or "")
        
        # Run the extraction workflow
        result = await pdf_service.run()
        
        # Update status to completed
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["message"] = "PDF extraction completed successfully"
        job_status[job_id]["result"] = result
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        # Update status to failed
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["message"] = f"Error: {str(e)}"
        job_status[job_id]["error"] = str(e)
        
        logger.error(f"Job {job_id} failed: {str(e)}")


def main():
    """Main entry point for the service."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        # reload=True,
        log_level="info"
    )


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Simple server runner for PDF extraction and viewing service
"""
import sys
import uvicorn
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    # Import the FastAPI app from main module
    try:
        from main import app
    except ImportError:
        # Alternative import method if running from different location
        sys.path.insert(0, str(Path(__file__).parent))
        from src.main import app
    
    print("Starting PDF Extraction & Viewing Service on port 8000...")
    print("Available endpoints:")
    print("  - PDF Extraction: POST /extract")
    print("  - Individual Extraction: POST /extract-individual") 
    print("  - PDF Viewer: POST /view-pdf")
    print("  - PDF Viewer (GET): GET /view-pdf/{file_path}")
    print("  - Health Check: GET /health")
    print("  - Service Info: GET /")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
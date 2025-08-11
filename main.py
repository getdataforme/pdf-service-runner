#!/usr/bin/env python3
"""
Simple main entry point for Replit deployment
"""

import os
import sys
import uvicorn
from pathlib import Path

# Ensure required directories exist
directories = ['logs', 'outputs', 'temp_individual_pdfs', 'pdfs/orange']
for directory in directories:
    Path(directory).mkdir(parents=True, exist_ok=True)

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Set default port
port = int(os.environ.get('PORT', 8000))

if __name__ == "__main__":
    # Import the FastAPI app
    from main import app

    print("🚀 Starting PDF Extraction Service...")
    print(f"Server will be available on port {port}")
    print("Available endpoints:")
    print("  - Health Check: GET /health")
    print("  - Service Info: GET /")
    print("  - PDF Extraction: POST /extract")
    print("  - Individual Extraction: POST /extract-individual")
    print("  - PDF Viewer: POST /view-pdf")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

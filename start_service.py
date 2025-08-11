#!/usr/bin/env python3
"""
Startup script for the PDF Extraction Service with PDF Viewer

This script serves as the entry point for the PDF extraction service.
It sets up the Python path and launches the FastAPI application with
both PDF extraction and PDF viewing capabilities.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path for proper imports
current_dir = Path(__file__).parent
src_dir = current_dir / 'src'
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(current_dir))

def main():
    """Main entry point for the PDF extraction and viewing service."""
    try:
        print("Starting PDF Extraction & Viewing Service...")
        print("Features available:")
        print("  - PDF document extraction")
        print("  - Individual PDF processing")
        print("  - PDF document viewing from GCS")
        print("  - Health monitoring")
        print()
        
        # Import and run the main application
        from src.main import main as app_main
        app_main()
    except ImportError as e:
        print(f"Error importing main application: {e}")
        print("Make sure you're running this script from the pdf-service-runner directory")
        print("and that all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

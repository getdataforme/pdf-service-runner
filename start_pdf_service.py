#!/usr/bin/env python3
"""
Unified PDF Service Launcher

This script starts the PDF extraction and viewing service with all features enabled.
It provides a single entry point for the entire PDF processing workflow.
"""

import os
import sys
import uvicorn
from pathlib import Path

def setup_environment():
    """Set up the Python path and environment for the service."""
    current_dir = Path(__file__).parent
    src_dir = current_dir / 'src'
    
    # Add both current and src directories to Python path
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(src_dir))
    
    print("PDF Service Environment Setup:")
    print(f"  Current directory: {current_dir}")
    print(f"  Source directory: {src_dir}")
    print(f"  Python path updated")
    print()

def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import fastapi
        import uvicorn
        import google.cloud.storage
        print("✓ Core dependencies available")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Please install dependencies: pip install -r requirements.txt")
        return False

def main():
    """Main entry point for the unified PDF service."""
    print("=" * 60)
    print("    PDF EXTRACTION & VIEWING SERVICE")
    print("=" * 60)
    print()
    
    # Set up environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check for environment variables
    env_vars_ok = True
    if not os.getenv("GCP_CREDENTIALS_JSON"):
        print("⚠️  Warning: GCP_CREDENTIALS_JSON not found")
        print("   PDF viewing will use mock service")
        env_vars_ok = False
    else:
        print("✓ GCP credentials configured")
    
    if env_vars_ok:
        print("✓ Environment configuration complete")
    print()
    
    try:
        # Import the FastAPI app
        from src.main import app
        
        print("Starting Unified PDF Service...")
        print("🚀 Service Features:")
        print("   • PDF Document Extraction")
        print("   • Individual PDF Processing") 
        print("   • PDF Document Viewing")
        print("   • Health Monitoring")
        print("   • Job Status Tracking")
        print()
        print("📡 Available Endpoints:")
        print("   • POST /extract - Bulk PDF extraction")
        print("   • POST /extract-individual - Single PDF processing")
        print("   • POST /view-pdf - PDF viewer (JSON)")
        print("   • GET /view-pdf/{file_path} - PDF viewer (URL)")
        print("   • GET /health - Service health check")
        print("   • GET /status/{job_id} - Job status")
        print("   • GET /jobs - List all jobs")
        print("   • GET / - Service information")
        print()
        print("🌐 Server starting on http://localhost:8000")
        print("📖 API Documentation: http://localhost:8000/docs")
        print("=" * 60)
        
        # Start the server
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Error importing application: {e}")
        print("Make sure you're running this script from the pdf-service-runner directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Setup script for PDF viewer service
"""

import os
import sys
import subprocess

def setup_environment():
    """Setup the environment for the PDF viewer service"""
    print("Setting up PDF Viewer Service...")
    
    # Check if we're in the right directory
    if not os.path.exists("src/main.py"):
        print("Error: Please run this script from the pdf-service-runner directory")
        sys.exit(1)
    
    # Install dependencies
    print("Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("Dependencies installed successfully!")
    except subprocess.CalledProcessError:
        print("Failed to install dependencies. Please install manually:")
        print("pip install -r requirements.txt")
        return False
    
    # Check for environment variables
    print("\nChecking environment configuration...")
    
    env_file = "../.env"
    if os.path.exists(env_file):
        print(f"Found .env file at {env_file}")
    else:
        print("Warning: No .env file found. Create one with your GCP credentials:")
        print("GCP_CREDENTIALS_JSON='{\"type\": \"service_account\", ...}'")
    
    print("\nSetup complete!")
    print("\nTo start the PDF service:")
    print("python run_server.py")
    print("\nTo test the service:")
    print("python test_pdf_viewer.py")
    
    return True

if __name__ == "__main__":
    setup_environment()

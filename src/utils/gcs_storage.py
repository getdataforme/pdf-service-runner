"""
Google Cloud Storage utilities for PDF operations
"""

import base64
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from datetime import timedelta
import json
import os
from dotenv import load_dotenv
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger()


def get_gcs_client():
    """
    Creates and returns a GCS client using credentials from an environment variable
    containing JSON credentials (not a file path).

    Returns:
        storage.Client: Configured GCS client.

    Raises:
        ValueError: If GCS credentials JSON is missing or invalid.
    """
    json_str = os.getenv("GCP_CREDENTIALS_JSON")
    if not json_str:
        raise ValueError("Missing GCP_CREDENTIALS_JSON environment variable. Set it to the JSON credentials string.")

    try:
        credentials_info = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON in GCP_CREDENTIALS_JSON environment variable.") from e

    return storage.Client.from_service_account_info(credentials_info)


def get_pdf_from_gcp(bucket_name: str, file_path: str) -> str:
    """
    Retrieve PDF file from GCP bucket and encode as base64.
    
    Args:
        bucket_name: Name of the GCS bucket
        file_path: Path to the file within the bucket
        
    Returns:
        Base64 encoded PDF content
        
    Raises:
        Exception: If file retrieval fails
    """
    try:
        logger.info(f"Retrieving PDF from GCS: {bucket_name}/{file_path}")
        client = get_gcs_client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(file_path)
        
        if not blob.exists():
            raise FileNotFoundError(f"File not found in GCS: {bucket_name}/{file_path}")
            
        pdf_content = blob.download_as_bytes()
        logger.info(f"Successfully retrieved PDF file: {len(pdf_content)} bytes")
        
        return base64.b64encode(pdf_content).decode('utf-8')
        
    except Exception as e:
        logger.error(f"Failed to retrieve PDF from GCS: {str(e)}")
        raise


def check_file_exists(bucket_name: str, file_path: str) -> bool:
    """
    Check if a file exists in the GCS bucket.
    
    Args:
        bucket_name: Name of the GCS bucket
        file_path: Path to the file within the bucket
        
    Returns:
        True if file exists, False otherwise
    """
    try:
        client = get_gcs_client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(file_path)
        return blob.exists()
    except Exception as e:
        logger.error(f"Error checking file existence: {str(e)}")
        return False


def generate_pdf_view_url(blob_name, bucket_name=None):
    """Generates a signed URL for viewing a PDF file in the browser.
    
    Args:
        blob_name (str): The key (path) in the GCS bucket.
        bucket_name (str): The GCS bucket name (default: from environment variable).
    
    Returns:
        str: A signed URL that can be used to view the PDF in browser.
    
    Raises:
        ValueError: If the GCS bucket name is not set.
        GoogleCloudError: If there's an error generating the signed URL.
    """
    if bucket_name is None:
        bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("Missing GCS bucket name in environment variables.")
    
    client = get_gcs_client()
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Set content type to application/pdf and content disposition to inline for viewing
        blob.content_type = 'application/pdf'
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="GET",
            response_type='application/pdf',
            response_disposition='inline'
        )
        logger.info(f"Generated signed PDF view URL for: {blob_name}")
        return url
    except GoogleCloudError as e:
        logger.error(f"Failed to generate PDF view URL for {blob_name}: {str(e)}")
        raise GoogleCloudError(f"Failed to generate PDF view URL for {blob_name} in GCS bucket {bucket_name}: {str(e)}")

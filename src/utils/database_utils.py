"""
Database utilities for MongoDB and GCS operations

This module provides utilities for:
- MongoDB operations (find, update documents)
- Google Cloud Storage operations (download files)
- PDF metadata management
"""

import os
import json
from pathlib import Path
from pymongo import MongoClient
from google.cloud.exceptions import NotFound, GoogleCloudError
from google.cloud import storage
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re

# Load environment from root .env file
from .env_loader import load_root_env

load_root_env()  # This will ensure MONGO_URI is available


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


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


def download_file(key, local_path, bucket_name=None):
    """
    Downloads a file from the specified key in the GCS bucket to a local path.

    Args:
        key (str): The key (path) in the GCS bucket.
        local_path (str): The local file path to save the file.
        bucket_name (str): The GCS bucket name (default: from environment variable).

    Raises:
        ValueError: If the GCS bucket name is not set.
        NotFound: If the file is not found in the GCS bucket.
        GoogleCloudError: If there's an error downloading from GCS.
    """
    if bucket_name is None:
        bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("Missing GCS bucket name in environment variables.")
    
    client = get_gcs_client()
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(key)
        blob.download_to_filename(local_path)
    except NotFound:
        raise NotFound(f"File not found in GCS bucket {bucket_name}: {key}")
    except GoogleCloudError as e:
        raise GoogleCloudError(f"Failed to download file {key} from GCS bucket {bucket_name}: {str(e)}")


def get_mongo_client():
    """
    Creates and returns a MongoDB client using credentials from environment variables.

    Returns:
        MongoClient: Configured MongoDB client.
    """
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("Missing MONGO_URI environment variable.")
    return MongoClient(mongo_uri)


def find_many(query, db_name, collection_name="cases"):
    """
    Finds multiple documents matching the query.

    Args:
        query (dict): The query filter.
        db_name (str): The database name.
        collection_name (str): The collection name (default: "cases").

    Returns:
        list: List of found documents.
    """
    client = get_mongo_client()
    db = client[db_name]
    collection = db[collection_name]
    result = list(collection.find(query))
    client.close()
    return result


def update_document_with_extraction_results(doc_id, extraction_results, db_name='courts-database', collection_name="allcourts"):
    """
    Updates a MongoDB document with PDF extraction results.

    Args:
        doc_id (str): The MongoDB document ID.
        extraction_results (dict): The extraction results from PDF processing.
        db_name (str): The database name.
        collection_name (str): The collection name (default: "allcourts").

    Returns:
        bool: True if update was successful, False otherwise.
    """
    client = None
    try:
        from bson import ObjectId
        client = get_mongo_client()
        db = client[db_name]
        collection = db[collection_name]

        # Convert doc_id to ObjectId
        oid = ObjectId(doc_id)

        # Find document by ID
        document = collection.find_one({"_id": oid})
        if not document:
            print(f"Document {doc_id} not found")
            return False

        # Get doc_path from extraction_results
        doc_path = extraction_results.get("original_gcs_path")
        if not doc_path:
            print(f"No doc_path in extraction_results")
            return False

        # Find matching document in documents array
        for doc in document.get("documents", []):
            if doc.get("doc_path") == doc_path:
                # Update incident dates
                update_data = {
                    "$set": {
                        f"documents.$.incident_date": extraction_results.get("incident_date"),
                        f"documents.$.incident_end_date": extraction_results.get("incident_end_date")
                    }
                }
                result = collection.update_one(
                    {"_id": oid, "documents.doc_path": doc_path},
                    update_data
                )
                return result.modified_count > 0

        print(f"No document found with doc_path {doc_path}")
        return False

    except Exception as e:
        print(f"Error updating document {doc_id}: {e}")
        return False
    finally:
        if client:
            client.close()


def download_pdfs_from_gcp(county_name, document_type, date_to, date_from=None):
    """
    Download PDFs from GCP bucket to the local 'pdfs' folder.
    
    Args:
        county_name (str): Name of the county
        document_type (str): Type of document to filter by
        date_to (str): End date in YYYY-MM-DD format
        date_from (str, optional): Start date in YYYY-MM-DD format
        
    Returns:
        dict: Mapping of PDF filenames to document metadata
    """
    
    pdfs_folder = Path("pdfs")
    pdfs_folder.mkdir(exist_ok=True)
    
    print(f"Starting PDF download for:")
    print(f"  County: {county_name}")
    print(f"  Document Type: {document_type}")
    print(f"  Date To: {date_to}")
    
    # If date_from is not provided, use a default date (e.g., 1 year ago)
    if date_from is None:
        date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
        date_from_obj = date_to_obj - timedelta(days=365)  # 1 year before date_to
        date_from = date_from_obj.strftime("%Y-%m-%d")
    
    print(f"  Date From: {date_from}")
    
    # MongoDB query to fetch the document of specific type
    query = {
        "court_name": {"$regex": county_name, "$options": "i"},
        "documents.description": {"$regex": document_type, "$options": "i"}
    }
    

    print(f"MongoDB query: {query}")

    db_name = "courts-database"
    collection_name = "allcourts"
    
    try:
        documents = find_many(query, db_name, collection_name)
        print(f"Found {len(documents)} documents in MongoDB")
    except Exception as e:
        print(f"Error querying MongoDB: {e}")
        return {}
    
    # Extract keys from documents with their MongoDB document IDs
    pdfs_key_from_mongo = [
        {"doc_id": str(document["_id"]), "doc_path": doc["doc_path"]} 
        for document in documents 
        for doc in document.get("documents", []) 
        if "doc_path" in doc and doc["doc_path"]
    ]

    # # For testing purposes - you can comment this out in production
    # pdfs_key_from_mongo = [
    #     {"doc_id": "6891f0b15ff95ab7eaf4ff3a", "doc_path": "orangecounty/2025-CA-006718-O/2025-CA-006718-O_Complaint.pdf"},
    # ]

    print(f"Found {len(pdfs_key_from_mongo)} PDF keys to download")
    
    if not pdfs_key_from_mongo:
        print("No PDFs found to download. This could be because:")
        print("1. No documents match the county name, document type, or date range")
        print("2. The documents don't have PDF attachments")
        print("3. The database connection failed")
        return {}

    # Create county-specific folder
    county_folder = pdfs_folder / county_name
    county_folder.mkdir(exist_ok=True)
    print(f"Created/verified county folder: {county_folder}")

    # Create mapping file to link PDF files to MongoDB document IDs
    mapping_file = county_folder / "pdf_to_docid_mapping.json"
    pdf_mapping = {}

    downloaded_count = 0
    for pdf_info in pdfs_key_from_mongo:
        doc_id = pdf_info["doc_id"]
        key = pdf_info["doc_path"]
        parts = key.split('/')
        local_path = f"{county_folder}/{parts[1].replace('-', '_')}_{parts[3]}"
        try:
            download_file(key, str(local_path))
            print(f"✓ Downloaded {key} (doc_id: {doc_id}) to {local_path}")
            
            # Use the local filename as the mapping key to ensure perfect matching
            local_filename = Path(local_path).name
            print(f"  Mapping key: {local_filename}")
            
            # Add to mapping using the local filename as key
            pdf_mapping[local_filename] = {
                "doc_id": doc_id,
                "original_path": key,
                "local_path": str(local_path)
            }
            
            downloaded_count += 1
        except Exception as e:
            print(f"✗ Failed to download {key} (doc_id: {doc_id}): {e}")
    
    # Save the mapping file
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(pdf_mapping, f, indent=2, ensure_ascii=False)
    print(f"PDF to Document ID mapping saved to: {mapping_file}")
    print(f"Mapping contains {len(pdf_mapping)} entries:")
    for key, value in pdf_mapping.items():
        print(f"  {key} -> doc_id: {value['doc_id']}")
    
    print(f"Download complete: {downloaded_count}/{len(pdfs_key_from_mongo)} files downloaded successfully")
    
    return pdf_mapping  # Return the mapping for further processing

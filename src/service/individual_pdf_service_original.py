"""
Individual PDF Service Module

Handles single PDF document extraction following the exact same procedure as batch extraction.
This ensures consistency between individual and batch processing workflows.
"""

import os
import json
import asyncio
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

from ..utils.logger import setup_logger
from ..utils.gcs_utils import download_file
from ..extractors.pdf_court_extractor import PDFCourtExtractor
from ..utils.database_utils import update_document_with_extraction_results


class IndividualPDFService:
    """
    Service for processing individual PDF documents using the same extraction
    procedure as the original batch processing.
    
    This maintains consistency with the original PDFCourtExtractor workflow:
    1. Download PDF from GCS
    2. Extract using PDFCourtExtractor.extract_from_pdf()
    3. Save individual result as JSON
    4. Update MongoDB using update_document_with_extraction_results()
    """
    
    def __init__(self):
        """Initialize the individual PDF service."""
        self.logger = setup_logger()
        
        # Create temp directory for individual downloads
        self.temp_dir = Path("temp_individual_pdfs")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Create outputs directory for individual results
        self.outputs_dir = Path("outputs")
        self.outputs_dir.mkdir(exist_ok=True)

    async def extract_individual_document(self, case_id: str, mongo_id: str, doc_path: str, document_description: str) -> Dict[str, Any]:
        """
        Extract data from a single PDF document using the original extraction procedure.
        
        This method follows the exact same workflow as the original batch extraction:
        - Uses PDFCourtExtractor.extract_from_pdf() method
        - Saves individual results as JSON files
        - Updates MongoDB using the same database utility function
        
        Args:
            case_id: PostgreSQL case ID  
            mongo_id: MongoDB case ObjectId (if available)
            doc_path: GCS path to the PDF document
            document_description: Human-readable description of the document
            
        Returns:
            Dict containing extraction results in the same format as batch extraction
        """
        local_pdf_path = None
        
        try:
            self.logger.info(f"Starting individual PDF extraction for case {case_id}")
            self.logger.info(f"  MongoDB ID: {mongo_id}")
            self.logger.info(f"  Document path: {doc_path}")
            self.logger.info(f"  Description: {document_description}")
            
            # Step 1: Download the individual PDF from GCS
            local_pdf_path = await self._download_individual_pdf(doc_path)
            
            # Step 2: Extract data using the original PDFCourtExtractor method
            extraction_result = await self._extract_using_original_method(local_pdf_path, doc_path)
            
            # Step 3: Save individual result (following original batch procedure)
            self._save_individual_result(extraction_result)
            
            # Step 4: Update MongoDB with extraction results (if MongoDB ID is available)
            mongodb_updated = False
            if mongo_id:
                mongodb_updated = await self._update_mongodb_original_method(mongo_id, extraction_result)
            else:
                self.logger.warning(f"No MongoDB ID available for case {case_id}, skipping database update")
            
            # Step 5: Clean up temporary file
            if local_pdf_path:
                self._cleanup_temp_file(local_pdf_path)
            
            # Return result with enhanced metadata for API response
            return self._format_api_response(
                case_id, mongo_id, doc_path, document_description, 
                extraction_result, mongodb_updated, success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in individual PDF extraction for case {case_id}: {str(e)}")
            
            # Clean up on error
            if local_pdf_path:
                self._cleanup_temp_file(local_pdf_path)
            
            # Return error result in the same format as original batch extraction
            error_result = {
                'pdf_file': Path(doc_path).name,
                'county': 'unknown',
                'error': str(e),
                'extraction_timestamp': datetime.now().isoformat()
            }
            
            return self._format_api_response(
                case_id, mongo_id, doc_path, document_description, 
                error_result, mongodb_updated=False, success=False
            )

    async def _download_individual_pdf(self, doc_path: str) -> str:
        """
        Download a single PDF from GCS.
        
        Args:
            doc_path: GCS path to the PDF document
            
        Returns:
            Local path to the downloaded PDF
        """
        try:
            # Extract filename from doc_path
            filename = Path(doc_path).name
            if not filename.endswith('.pdf'):
                filename = f"{filename}.pdf"
            
            local_path = self.temp_dir / filename
            
            self.logger.info(f"Downloading PDF from GCS: {doc_path}")
            
            # Run the download in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                download_file,
                doc_path,
                str(local_path)
            )
            
            if not local_path.exists():
                raise FileNotFoundError(f"Failed to download PDF from {doc_path}")
            
            self.logger.info(f"Successfully downloaded PDF to: {local_path}")
            return str(local_path)
            
        except Exception as e:
            self.logger.error(f"Error downloading PDF from {doc_path}: {str(e)}")
            raise e

    async def _extract_using_original_method(self, local_pdf_path: str, original_gcs_path: str) -> Dict[str, Any]:
        """
        Extract data from PDF using the original PDFCourtExtractor.extract_from_pdf() method.
        
        This ensures the same extraction logic, patterns, and data format as batch processing.
        
        Args:
            local_pdf_path: Local path to the PDF file
            original_gcs_path: Original GCS path (for metadata)
            
        Returns:
            Dictionary containing extracted data in original format
        """
        try:
            self.logger.info(f"Extracting data from PDF using original method: {local_pdf_path}")
            
            # Initialize extractor with patterns (if available)
            # Look for patterns file - try different county patterns
            patterns_file = None
            patterns_dir = Path("patterns")
            if patterns_dir.exists():
                # Try to find appropriate patterns file
                for pattern_file in patterns_dir.glob("*_patterns.json"):
                    patterns_file = str(pattern_file)
                    break
            
            extractor = PDFCourtExtractor(patterns_file)
            
            # Run extraction in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                extractor.extract_from_pdf,
                local_pdf_path,
                "individual"  # county name for individual extraction
            )
            
            # Add MongoDB-specific metadata (same as batch processing)
            result['original_gcs_path'] = original_gcs_path
            
            self.logger.info(f"Extraction completed successfully")
            self.logger.info(f"  Found incident date: {result.get('incident_date', 'None')}")
            self.logger.info(f"  Incident end date: {result.get('incident_end_date', 'None')}")
            self.logger.info(f"  Total extracted fields: {len(result.get('extracted_data', {}))}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting data from PDF {local_pdf_path}: {str(e)}")
            raise e

    def _save_individual_result(self, result: Dict[str, Any]):
        """
        Save individual extraction result as JSON file.
        
        This follows the same saving pattern as the original batch processing.
        """
        try:
            county_name = result.get('county', 'individual')
            output_dir = self.outputs_dir / county_name
            output_dir.mkdir(exist_ok=True)
            
            pdf_name = Path(result.get('pdf_file', 'unknown')).stem
            output_file = output_dir / f"{pdf_name}.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved individual result to: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving individual result: {str(e)}")

    async def _update_mongodb_original_method(self, mongo_id: str, extraction_result: Dict[str, Any]) -> bool:
        """
        Update MongoDB document with extraction results using the original method.
        
        This uses the same update_document_with_extraction_results function as batch processing.
        
        Args:
            mongo_id: MongoDB ObjectId (24-character hex string)
            extraction_result: Results from PDF extraction
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            self.logger.info(f"Updating MongoDB document {mongo_id} with extraction results")
            
            # Validate that mongo_id is a valid ObjectId string
            if not mongo_id or len(mongo_id) != 24:
                self.logger.error(f"Invalid MongoDB ObjectId: {mongo_id}")
                return False
            
            # Run the database update in a thread to avoid blocking
            # Use the exact same function as the original batch processing
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                update_document_with_extraction_results,
                mongo_id,
                extraction_result
            )
            
            if success:
                self.logger.info(f"✓ Successfully updated MongoDB document {mongo_id}")
            else:
                self.logger.warning(f"✗ Failed to update MongoDB document {mongo_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error updating MongoDB document {mongo_id}: {str(e)}")
            return False

    def _cleanup_temp_file(self, file_path: str):
        """Clean up temporary downloaded file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            self.logger.warning(f"Could not clean up temporary file {file_path}: {str(e)}")

    def _format_api_response(self, case_id: str, mongo_id: str, doc_path: str, 
                           document_description: str, extraction_result: Dict[str, Any], 
                           mongodb_updated: bool, success: bool) -> Dict[str, Any]:
        """
        Format the extraction result for API response.
        
        This maintains compatibility with the frontend while including all original extraction data.
        """
        response = {
            # API metadata
            "case_id": case_id,
            "mongo_id": mongo_id,
            "doc_path": doc_path,
            "document_description": document_description,
            "extraction_timestamp": datetime.now().isoformat(),
            "extraction_success": success,
            "mongodb_updated": mongodb_updated,
            "status": "completed" if success else "failed",
            
            # Original extraction data (preserved exactly as batch processing)
            "pdf_file": extraction_result.get("pdf_file"),
            "county": extraction_result.get("county"),
            "incident_date": extraction_result.get("incident_date"),
            "incident_end_date": extraction_result.get("incident_end_date"),
            "incident_source_field": extraction_result.get("incident_source_field"),
            "all_incident_dates": extraction_result.get("all_incident_dates", []),
            "extracted_data": extraction_result.get("extracted_data", {}),
            "original_gcs_path": extraction_result.get("original_gcs_path"),
        }
        
        # Include error information if present
        if "error" in extraction_result:
            response["error"] = extraction_result["error"]
            response["message"] = f"Failed to extract data from {document_description}: {extraction_result['error']}"
        else:
            response["message"] = f"Successfully extracted data from {document_description}"
        
        return response

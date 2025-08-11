"""
Individual PDF Service Module

Handles extraction of data from individual PDF documents.
"""

import os
import asyncio
from typing import Dict, Any
from pathlib import Path

from ..utils.logger import setup_logger
from ..utils.database_utils import download_file, update_document_with_extraction_results
from ..extractors.pdf_court_extractor import PDFCourtExtractor


class IndividualPDFService:
    """
    Service class for processing individual PDF documents.
    
    Handles downloading and extracting data from a single PDF document.
    """
    
    def __init__(self):
        """Initialize the individual PDF service."""
        self.logger = setup_logger()
        
    async def extract_individual_document(self, case_id: str, mongo_id: str, doc_path: str, document_description: str) -> Dict[str, Any]:
        """
        Extract data from a single PDF document.
        
        Args:
            case_id: PostgreSQL case ID  
            mongo_id: MongoDB case ObjectId (if available)
            doc_path: GCS path to the PDF document
            document_description: Human-readable description of the document
            
        Returns:
            Dict containing extraction results
        """
        try:
            self.logger.info(f"Starting individual PDF extraction for case {case_id}")
            self.logger.info(f"  MongoDB ID: {mongo_id}")
            self.logger.info(f"  Document path: {doc_path}")
            self.logger.info(f"  Description: {document_description}")
            
            # Step 1: Download the individual PDF from GCS
            local_pdf_path = await self._download_individual_pdf(doc_path)
            
            # Step 2: Extract data from the PDF
            extraction_result = await self._extract_pdf_data(local_pdf_path, doc_path)
            
            # Step 3: Update MongoDB with extraction results (if MongoDB ID is available)
            mongodb_updated = False
            if mongo_id:
                mongodb_updated = await self._update_mongodb(mongo_id, doc_path, extraction_result)
            else:
                self.logger.warning(f"No MongoDB ID available for case {case_id}, skipping database update")
            
            # Step 4: Clean up temporary file
            self._cleanup_temp_file(local_pdf_path)
            
            return {
                "case_id": case_id,
                "mongo_id": mongo_id,
                "doc_path": doc_path,
                "incident_date": extraction_result.get("incident_date"),
                "incident_end_date": extraction_result.get("incident_end_date"),
                "extraction_success": True,
                "mongodb_updated": mongodb_updated,
                "message": f"Successfully extracted data from {document_description}"
            }
            
        except Exception as e:
            self.logger.error(f"Error in individual PDF extraction: {str(e)}")
            raise e

    async def _download_individual_pdf(self, doc_path: str) -> str:
        """
        Download a single PDF from GCS.
        
        Args:
            doc_path: GCS path to the PDF document
            
        Returns:
            Local path to the downloaded PDF
        """
        try:
            # Create temp directory for individual downloads
            temp_dir = Path("temp_individual_pdfs")
            temp_dir.mkdir(exist_ok=True)
            
            # Extract filename from doc_path
            filename = Path(doc_path).name
            if not filename.endswith('.pdf'):
                filename = f"{filename}.pdf"
            
            local_path = temp_dir / filename
            
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

    async def _extract_pdf_data(self, local_pdf_path: str, original_gcs_path: str) -> Dict[str, Any]:
        """
        Extract data from the PDF file.
        
        Args:
            local_pdf_path: Local path to the PDF file
            original_gcs_path: Original GCS path (for metadata)
            
        Returns:
            Dictionary containing extracted data
        """
        try:
            self.logger.info(f"Extracting data from PDF: {local_pdf_path}")
            
            # Initialize extractor
            extractor = PDFCourtExtractor()
            
            # Run extraction in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                extractor.extract_from_pdf,
                local_pdf_path,
                "individual"  # county name for individual extraction
            )
            
            # Add original GCS path to result for MongoDB update
            result['original_gcs_path'] = original_gcs_path
            
            self.logger.info(f"Extraction completed. Found incident date: {result.get('incident_date', 'None')}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting data from PDF {local_pdf_path}: {str(e)}")
            raise e

    async def _update_mongodb(self, mongo_id: str, doc_path: str, extraction_result: Dict[str, Any]) -> bool:
        """
        Update MongoDB document with extraction results.
        
        Args:
            mongo_id: MongoDB ObjectId (24-character hex string)
            doc_path: GCS path to the document
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

    def _cleanup_temp_file(self, local_pdf_path: str) -> None:
        """
        Clean up temporary PDF file.
        
        Args:
            local_pdf_path: Path to the temporary PDF file
        """
        try:
            if os.path.exists(local_pdf_path):
                os.remove(local_pdf_path)
                self.logger.info(f"Cleaned up temporary file: {local_pdf_path}")
        except Exception as e:
            self.logger.warning(f"Failed to clean up temporary file {local_pdf_path}: {str(e)}")

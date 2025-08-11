"""
PDF Service Module

Handles the orchestration of PDF downloading and extraction processes.
"""

import os
import asyncio
from typing import Dict, Any
from pathlib import Path

from ..utils.logger import setup_logger
from ..utils.database_utils import download_pdfs_from_gcp
from ..extractors.pdf_court_extractor import PDFCourtExtractor


class PDFService:
    """
    Main service class for PDF processing workflow.
    
    Coordinates the download of PDFs from GCS and extraction of data.
    """
    
    def __init__(self, county_name: str, document_type: str, date_to: str, date_from: str = None):
        """
        Initialize the PDF service.
        
        Args:
            county_name: Name of the county to process
            document_type: Type of document to filter by
            date_to: End date for document filtering (YYYY-MM-DD)
            date_from: Start date for document filtering (YYYY-MM-DD, optional)
        """
        self.county_name = county_name
        self.document_type = document_type
        self.date_to = date_to
        self.date_from = date_from
        self.logger = setup_logger()
        
        # Set up paths
        self.pdf_folder = Path("pdfs") / county_name
        self.patterns_file = Path("patterns") / f"{county_name}_patterns.json"

    async def run(self) -> Dict[str, Any]:
        """
        Main method to run the PDF extraction process.
        
        Returns:
            Dict containing process results and statistics
        """
        try:
            self.logger.info(f"Starting PDF processing workflow for {self.county_name}")
            
            # Step 1: Download PDFs from GCP
            pdf_mapping = await self._download_pdfs()
            
            # Step 2: Extract data from PDFs
            extraction_result = await self._extract_data()
            
            return {
                "success": True,
                "county_name": self.county_name,
                "document_type": self.document_type,
                "date_range": {
                    "from": self.date_from,
                    "to": self.date_to
                },
                "pdf_download": {
                    "total_available": len(pdf_mapping),
                    "successfully_downloaded": len([k for k, v in pdf_mapping.items() if Path(v['local_path']).exists()])
                },
                "extraction_result": extraction_result
            }
            
        except Exception as e:
            self.logger.error(f"Error in PDF processing workflow: {str(e)}")
            raise e

    async def _download_pdfs(self) -> Dict[str, Any]:
        """
        Download PDFs from GCP based on parameters.
        
        Returns:
            Dictionary mapping PDF filenames to metadata
        """
        try:
            self.logger.info(f"Downloading PDFs for {self.county_name}")
            self.logger.info(f"  Document type: {self.document_type}")
            self.logger.info(f"  Date range: {self.date_from} to {self.date_to}")
            
            # Run the download in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            pdf_mapping = await loop.run_in_executor(
                None,
                download_pdfs_from_gcp,
                self.county_name,
                self.document_type,
                self.date_to,
                self.date_from
            )
            
            # Verify download results
            if os.path.exists(self.pdf_folder):
                pdf_files = [f for f in os.listdir(self.pdf_folder) if f.endswith('.pdf')]
                self.logger.info(f"PDF download completed. Found {len(pdf_files)} PDF files in {self.pdf_folder}")
            else:
                self.logger.warning(f"PDF download completed but no folder created at {self.pdf_folder}")
                pdf_mapping = {}
            
            return pdf_mapping
            
        except Exception as e:
            self.logger.error(f"Error downloading PDFs: {str(e)}")
            raise e

    async def _extract_data(self) -> Dict[str, Any]:
        """
        Extract data from downloaded PDFs using the PDFCourtExtractor.
        
        Returns:
            Dictionary containing extraction results and statistics
        """
        try:
            self.logger.info(f"Starting data extraction for {self.county_name}")
            
            # Verify PDF folder exists
            if not self.pdf_folder.exists():
                self.logger.warning(f"PDF folder not found: {self.pdf_folder}")
                self.pdf_folder.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created PDF folder: {self.pdf_folder}")
            
            # Check for PDF files
            pdf_files = [f for f in os.listdir(self.pdf_folder) if f.endswith('.pdf')]
            
            if not pdf_files:
                return self._create_empty_result(f"No PDF files found in {self.pdf_folder}")
            
            self.logger.info(f"Found {len(pdf_files)} PDF files to process")
            
            # Initialize extractor with patterns
            extractor = PDFCourtExtractor(str(self.patterns_file) if self.patterns_file.exists() else None)
            
            # Run extraction in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                extractor.extract_batch,
                str(self.pdf_folder),
                self.county_name,
                True,  # save_individual
                True   # update_mongodb
            )
            
            self.logger.info(f"Data extraction completed. Processed {len(results)} files")
            
            return self._create_extraction_summary(results)
            
        except Exception as e:
            self.logger.error(f"Error extracting data: {str(e)}")
            raise e
    
    def _create_empty_result(self, message: str) -> Dict[str, Any]:
        """Create an empty result structure with a message."""
        return {
            "total_files": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "results": [],
            "message": message
        }
    
    def _create_extraction_summary(self, results: list) -> Dict[str, Any]:
        """Create a summary of extraction results."""
        success_count = len([r for r in results if 'error' not in r])
        error_count = len(results) - success_count
        
        # Count files with incident dates found
        incident_dates_found = len([
            r for r in results 
            if 'error' not in r and r.get('incident_date') and r.get('incident_date') != 'NA'
        ])
        
        return {
            "total_files": len(results),
            "successful_extractions": success_count,
            "failed_extractions": error_count,
            "incident_dates_found": incident_dates_found,
            "results": results,
            "summary": {
                "county": self.county_name,
                "extraction_rate": f"{success_count}/{len(results)} ({(success_count/len(results)*100):.1f}%)" if results else "0/0 (0.0%)",
                "incident_detection_rate": f"{incident_dates_found}/{success_count} ({(incident_dates_found/success_count*100):.1f}%)" if success_count > 0 else "0/0 (0.0%)"
            }
        }
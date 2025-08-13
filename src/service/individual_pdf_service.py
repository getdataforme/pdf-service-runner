"""
Individual PDF Service Module

Handles single PDF document extraction following the exact same procedure as batch extraction.
This ensures consistency between individual and batch processing workflows.
"""

import os
import json
import asyncio
import psycopg2
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from ..utils.logger import setup_logger
from ..utils.database_utils import download_file, update_document_with_extraction_results
from ..utils.env_loader import load_root_env  # Load environment from root .env
from ..extractors.pdf_court_extractor import PDFCourtExtractor


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

        # PostgreSQL connection configuration from DATABASE_URL
        self.pg_config = self._parse_database_url()

    def _parse_database_url(self) -> Dict[str, str]:
        """
        Parse DATABASE_URL from environment variable into psycopg2 connection parameters.

        Expected format: postgresql://user:password@host:port/database?sslmode=require
        """
        database_url = os.getenv('DATABASE_URL')

        if not database_url:
            # Fallback to individual environment variables
            self.logger.warning("DATABASE_URL not found, using individual PostgreSQL environment variables")
            return {
                'host': os.getenv('POSTGRES_HOST', 'localhost'),
                'port': os.getenv('POSTGRES_PORT', '5432'),
                'database': os.getenv('POSTGRES_DB', 'legal_data_manager'),
                'user': os.getenv('POSTGRES_USER', 'postgres'),
                'password': os.getenv('POSTGRES_PASSWORD', 'password'),
                'connect_timeout': 30,
                'keepalives_idle': 600,
                'keepalives_interval': 30,
                'keepalives_count': 3
            }

        try:
            # Parse the DATABASE_URL
            parsed = urlparse(database_url)

            config = {
                'host': parsed.hostname,
                'port': str(parsed.port) if parsed.port else '5432',
                'database': parsed.path[1:] if parsed.path else 'postgres',  # Remove leading slash
                'user': parsed.username,
                'password': parsed.password,
                # Connection optimization settings
                'connect_timeout': 30,
                'keepalives_idle': 600,
                'keepalives_interval': 30,
                'keepalives_count': 3
            }

            # Handle SSL mode if present in query parameters
            if parsed.query:
                query_params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
                if 'sslmode' in query_params:
                    config['sslmode'] = query_params['sslmode']

            self.logger.info(f"Parsed PostgreSQL config from DATABASE_URL: host={config['host']}, database={config['database']}")
            return config

        except Exception as e:
            self.logger.error(f"Error parsing DATABASE_URL: {str(e)}")
            # Fallback to default values
            return {
                'host': 'localhost',
                'port': '5432',
                'database': 'legal_data_manager',
                'user': 'postgres',
                'password': 'password',
                'connect_timeout': 30,
                'keepalives_idle': 600,
                'keepalives_interval': 30,
                'keepalives_count': 3
            }

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
                self.logger.warning(f"No MongoDB ID available for case {case_id}, skipping MongoDB update")

            # Step 5: Update PostgreSQL with extraction results
            postgres_updated = await self._update_postgresql_document(case_id, doc_path, extraction_result)

            # Step 6: Clean up temporary file
            if local_pdf_path:
                self._cleanup_temp_file(local_pdf_path)

            # Return result with enhanced metadata for API response
            return self._format_api_response(
                case_id, mongo_id, doc_path, document_description, 
                extraction_result, mongodb_updated, postgres_updated, success=True
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
                error_result, mongodb_updated=False, postgres_updated=False, success=False
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

            # Debug: Log what we're sending to MongoDB
            self.logger.info(f"MongoDB update data:")
            self.logger.info(f"  original_gcs_path: {extraction_result.get('original_gcs_path')}")
            self.logger.info(f"  incident_date: {extraction_result.get('incident_date')}")
            self.logger.info(f"  incident_end_date: {extraction_result.get('incident_end_date')}")

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

    async def _update_postgresql_document(self, case_id: str, doc_path: str, extraction_result: Dict[str, Any]) -> bool:
        """
        Update the PostgreSQL court_cases table with extracted incident dates.

        This updates the specific document within the documents JSON array.

        Args:
            case_id: PostgreSQL case ID
            doc_path: Document path to identify the specific document
            extraction_result: Results from PDF extraction

        Returns:
            True if update was successful, False otherwise
        """
        try:
            self.logger.info(f"Updating PostgreSQL case {case_id} document {doc_path}")

            # Extract incident dates and emails from the extraction result
            incident_date = extraction_result.get('incident_date')
            incident_end_date = extraction_result.get('incident_end_date')
            emails = extraction_result.get('emails')

            # Debug: Log what we extracted
            self.logger.info(f"Extracted for PostgreSQL update:")
            self.logger.info(f"  incident_date: {incident_date}")
            self.logger.info(f"  incident_end_date: {incident_end_date}")
            self.logger.info(f"  emails: {emails}")

            if not incident_date and not incident_end_date and not emails:
                self.logger.warning(f"No incident dates or emails found in extraction result for {doc_path}")
                return False

            # Run the database update in a thread with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(
                        None,
                        self._update_postgresql_sync,
                        case_id,
                        doc_path,
                        incident_date,
                        incident_end_date,
                        emails,
                        extraction_result.get('extraction_timestamp')
                    )

                    if success:
                        self.logger.info(f"✓ Successfully updated PostgreSQL case {case_id} document {doc_path}")
                        return True
                    else:
                        self.logger.warning(f"✗ Failed to update PostgreSQL case {case_id} document {doc_path} (attempt {attempt + 1})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)  # Wait before retry

                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed for PostgreSQL update: {str(e)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)  # Wait longer before retry
                    else:
                        raise e

            self.logger.error(f"✗ All {max_retries} attempts failed for PostgreSQL case {case_id}")
            return False

        except Exception as e:
            self.logger.error(f"✗ Error updating PostgreSQL case {case_id}: {str(e)}")
            return False

    def _update_postgresql_sync(self, case_id: str, doc_path: str, incident_date: str, 
                               incident_end_date: str, emails: str, extraction_timestamp: str) -> bool:
        """
        Synchronous PostgreSQL update function to run in executor.
        """
        conn = None
        cursor = None
        try:
            # Connect to PostgreSQL with proper connection settings
            conn = psycopg2.connect(
                **self.pg_config,
                application_name='pdf_extraction_service'
            )

            # Set autocommit to False for transaction control
            conn.autocommit = False
            cursor = conn.cursor()

            # Get current documents JSON
            cursor.execute("SELECT documents FROM court_cases WHERE id = %s", (case_id,))
            result = cursor.fetchone()

            if not result:
                self.logger.error(f"Case {case_id} not found in PostgreSQL")
                return False

            documents_json = result[0]
            if not documents_json:
                self.logger.warning(f"No documents found for case {case_id}")
                return False

            # Parse documents JSON
            try:
                documents = json.loads(documents_json) if isinstance(documents_json, str) else documents_json
            except json.JSONDecodeError:
                self.logger.error(f"Invalid JSON in documents field for case {case_id}")
                return False

            # Find and update the specific document
            document_updated = False
            for doc in documents:
                if doc.get('doc_path') == doc_path:
                    # Update incident dates
                    if incident_date:
                        doc['incident_date'] = incident_date
                        self.logger.info(f"Updated incident_date to: {incident_date}")

                    if incident_end_date:
                        doc['incident_end_date'] = incident_end_date
                        self.logger.info(f"Updated incident_end_date to: {incident_end_date}")

                        # Update emails
                    self.logger.info(f"Emails parameter received: {emails}")
                    if emails:
                        doc['emails'] = emails
                        self.logger.info(f"Updated emails to: {emails}")
                    else:
                        self.logger.info("No emails to update (emails parameter is None or empty)")

                    # Add extraction metadata
                    doc['extraction_timestamp'] = extraction_timestamp
                    doc['extracted_by'] = 'individual_pdf_service'

                    document_updated = True
                    break

            if not document_updated:
                self.logger.warning(f"Document with path {doc_path} not found in case {case_id}")
                return False

            # Update the database with modified documents
            cursor.execute(
                "UPDATE court_cases SET documents = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (json.dumps(documents), case_id)
            )

            # Commit the transaction
            conn.commit()
            self.logger.info(f"PostgreSQL transaction committed for case {case_id}")

            return True

        except psycopg2.OperationalError as e:
            self.logger.error(f"PostgreSQL connection error: {str(e)}")
            if conn:
                conn.rollback()
            return False
        except psycopg2.Error as e:
            self.logger.error(f"PostgreSQL database error: {str(e)}")
            if conn:
                conn.rollback()
            return False
        except Exception as e:
            self.logger.error(f"PostgreSQL update error: {str(e)}")
            if conn:
                conn.rollback()
            return False
        finally:
            # Clean up resources in proper order
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def _cleanup_temp_file(self, file_path: str):
        """Clean up temporary downloaded file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            self.logger.warning(f"Could not clean up temporary file {file_path}: {str(e)}")

    def _format_api_response(self, case_id: str, mongo_id: str, doc_path: str, 
                           document_description: str, extraction_result: Optional[Dict[str, Any]], 
                           mongodb_updated: bool, postgres_updated: bool, success: bool) -> Dict[str, Any]:
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
            "status": "completed" if success else "failed",

            # Database update status
            "database_updates": {
                "mongodb_updated": mongodb_updated,
                "postgresql_updated": postgres_updated
            }
        }

        if extraction_result:
            # Original extraction data (preserved exactly as batch processing)
            response.update({
                "pdf_file": extraction_result.get("pdf_file"),
                "county": extraction_result.get("county"),
                "incident_date": extraction_result.get("incident_date"),
                "incident_end_date": extraction_result.get("incident_end_date"),
                "incident_source_field": extraction_result.get("incident_source_field"),
                "all_incident_dates": extraction_result.get("all_incident_dates", []),
                "emails": extraction_result.get("emails"),
                "extracted_data": extraction_result.get("extracted_data", {}),
                "original_gcs_path": extraction_result.get("original_gcs_path"),
            })

        # Include error information if present
        if extraction_result and "error" in extraction_result:
            response["error"] = extraction_result["error"]
            response["message"] = f"Failed to extract data from {document_description}: {extraction_result['error']}"
        elif success:
            # Enhanced message based on what was updated
            updates = []
            if mongodb_updated:
                updates.append('MongoDB')
            if postgres_updated:
                updates.append('PostgreSQL')

            if updates:
                response["message"] = f"Successfully extracted incident dates and emails for {document_description} (Updated: {' & '.join(updates)})"
            else:
                response["message"] = f"Successfully extracted data from {document_description}"
        else:
            response["message"] = f"Failed to extract data from {document_description}"

        return response

"""
PDF Viewer Service

Service for serving PDF documents from GCP storage using signed URLs.
"""

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from src.utils.gcs_storage import generate_pdf_view_url, check_file_exists
from src.utils.logger import setup_logger

logger = setup_logger()


class PDFViewerService:
    """Service for viewing PDF documents from GCP storage."""

    def __init__(self, default_bucket: str = "courts-bucket"):
        """
        Initialize the PDF viewer service.

        Args:
            default_bucket: Default GCS bucket name
        """
        self.default_bucket = default_bucket

    async def view_pdf(self, file_path: str, bucket_name: str = None) -> HTMLResponse:
        """
        Serve PDF viewer with signed URL for PDF content.

        Args:
            file_path: Path to the PDF file in GCS
            bucket_name: GCS bucket name (optional, uses default if not provided)

        Returns:
            HTML response containing PDF viewer with signed URL

        Raises:
            HTTPException: If PDF retrieval fails
        """
        if not bucket_name:
            bucket_name = self.default_bucket

        try:
            logger.info(f"Attempting to view PDF: {bucket_name}/{file_path}")

            # Check if file exists first
            if not check_file_exists(bucket_name, file_path):
                logger.error(f"PDF file not found: {bucket_name}/{file_path}")
                # Return "No PDF found" page instead of raising exception
                html_content = self._create_no_pdf_found_html(file_path)
                return HTMLResponse(
                    content=html_content,
                    status_code=200,
                    headers={"Content-Type": "text/html"}
                )

            # Generate signed URL for PDF viewing
            signed_url = generate_pdf_view_url(file_path, bucket_name)

            # Create HTML content with signed URL-based PDF viewer
            html_content = self._create_pdf_viewer_html_with_url(signed_url, file_path)

            logger.info(f"Successfully serving PDF viewer for: {file_path}")

            return HTMLResponse(
                content=html_content,
                status_code=200,
                headers={"Content-Type": "text/html"}
            )

        except Exception as e:
            logger.error(f"Error serving PDF viewer for {file_path}: {str(e)}")
            # Return "No PDF found" page instead of raising exception
            html_content = self._create_no_pdf_found_html(file_path)
            return HTMLResponse(
                content=html_content,
                status_code=200,
                headers={"Content-Type": "text/html"}
            )

    # Commented out old base64 approach - now using signed URLs only
    # def _create_pdf_viewer_html(self, pdf_base64: str, file_path: str) -> str:
    #     """
    #     Create simple HTML content for PDF viewer using base64 encoded content.
    #
    #     Args:
    #         pdf_base64: Base64 encoded PDF content
    #         file_path: Original file path for display
    #
    #     Returns:
    #         HTML string containing simple PDF viewer
    #     """
    #     return f"""
    #     <!DOCTYPE html>
    #     <html lang="en">
    #     <head>
    #         <meta charset="UTF-8">
    #         <meta name="viewport" content="width=device-width, initial-scale=1.0">
    #         <title>PDF Viewer - {file_path}</title>
    #         <style>
    #             body {{
    #                 margin: 0;
    #                 padding: 0;
    #                 height: 100vh;
    #                 display: flex;
    #                 flex-direction: column;
    #             }}
    #
    #             #pdfViewer {{
    #                 width: 100%;
    #                 height: 100%;
    #                 border: none;
    #             }}
    #         </style>
    #     </head>
    #     <body>
    #         <embed 
    #             id="pdfViewer" 
    #             src="data:application/pdf;base64,{pdf_base64}" 
    #             type="application/pdf"
    #         />
    #     </body>
    #     </html>
    #     """

    def _create_pdf_viewer_html_with_url(self, signed_url: str, file_path: str) -> str:
        """
        Create HTML content for PDF viewer using signed URL.

        Args:
            signed_url: Signed URL for the PDF file
            file_path: Original file path for display

        Returns:
            HTML string containing PDF viewer with signed URL
        """
        # Extract filename from path to avoid f-string backslash issues
        filename = file_path.split('/').pop().split('\\').pop() if file_path else 'document.pdf'
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>PDF Viewer - {filename}</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    display: flex;
                    flex-direction: column;
                    font-family: Arial, sans-serif;
                }}

                .header {{
                    background-color: #f5f5f5;
                    padding: 10px 20px;
                    border-bottom: 1px solid #ddd;
                    font-size: 14px;
                    color: #333;
                }}

                #pdfViewer {{
                    width: 100%;
                    height: calc(100vh - 50px);
                    border: none;
                }}

                .error-message {{
                    text-align: center;
                    padding: 50px;
                    color: #666;
                    font-size: 18px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                PDF Viewer: {filename}
            </div>
            <embed 
                id="pdfViewer" 
                src="{signed_url}" 
                type="application/pdf"
                onerror="document.getElementById('pdfViewer').style.display='none'; document.getElementById('errorMsg').style.display='block';"
            />
            <div id="errorMsg" class="error-message" style="display: none;">
                <h3>PDF Not Found</h3>
                <p>The requested PDF file could not be loaded.</p>
            </div>
        </body>
        </html>
        """

    def _create_no_pdf_found_html(self, file_path: str) -> str:
        """
        Create HTML content for "No PDF found" message.

        Args:
            file_path: Original file path for display

        Returns:
            HTML string for no PDF found page
        """
        # Extract filename from path
        filename = file_path.split('/').pop().split('\\').pop() if file_path else 'document.pdf'
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>PDF Not Found - {filename}</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    font-family: Arial, sans-serif;
                    background-color: #f8f9fa;
                }}

                .error-container {{
                    text-align: center;
                    padding: 40px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 500px;
                    margin: 20px;
                }}

                .error-icon {{
                    font-size: 64px;
                    color: #dc3545;
                    margin-bottom: 20px;
                }}

                .error-title {{
                    color: #333;
                    font-size: 24px;
                    margin-bottom: 10px;
                }}

                .error-message {{
                    color: #666;
                    font-size: 16px;
                    line-height: 1.5;
                    margin-bottom: 20px;
                }}

                .file-path {{
                    background-color: #f8f9fa;
                    padding: 10px;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 14px;
                    color: #666;
                    word-break: break-all;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">📄</div>
                <h1 class="error-title">No PDF Found</h1>
                <p class="error-message">
                    The requested PDF file could not be found or is not accessible.
                </p>
                <div class="file-path">
                    File: {filename}<br>
                    Path: {file_path}
                </div>
            </div>
        </body>
        </html>
        """
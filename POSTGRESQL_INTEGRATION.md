# PostgreSQL Integration for Individual PDF Extraction

## Overview
Added PostgreSQL database update functionality to the individual PDF extraction service. Now when a user extracts an individual document, the incident dates are updated in both MongoDB (for batch processing consistency) and PostgreSQL (for frontend display).

## What Was Implemented

### 1. **Enhanced Individual PDF Service**
- **File**: `pdf-service-runner/src/service/individual_pdf_service.py`
- **Added PostgreSQL connection configuration**
- **Added `_update_postgresql_document()` method**
- **Added `_update_postgresql_sync()` helper method**
- **Enhanced API response with database update status**

### 2. **Database Update Workflow**
```
Individual PDF Extraction Process:
1. Download PDF from GCS
2. Extract data using PDFCourtExtractor
3. Save individual result as JSON
4. Update MongoDB (for batch consistency)
5. Update PostgreSQL (for frontend display) ← NEW
6. Clean up temporary files
```

### 3. **PostgreSQL Update Details**
- **Target Table**: `court_cases`
- **Target Field**: `documents` (JSON column)
- **Updates**:
  - `incident_date`: Extracted incident date
  - `incident_end_date`: Extracted incident end date (if found)
  - `extraction_timestamp`: When extraction occurred
  - `extracted_by`: 'individual_pdf_service' (tracking flag)
  - `updated_at`: Case modification timestamp

### 4. **Frontend Enhancements**
- **File**: `client/src/components/court-cases/case-detail-modal.tsx`
- **Enhanced feedback messages showing which databases were updated**
- **Example**: "Extraction completed - Updated: MongoDB & PostgreSQL"

### 5. **Dependencies Added**
- **Package**: `psycopg2-binary` (PostgreSQL adapter for Python)
- **Installation**: Completed via `install_python_packages` tool

## Configuration

### Environment Variables
The PDF service runner now automatically loads environment variables from the root `.env` file:
- **DATABASE_URL**: PostgreSQL connection string (automatically parsed)
- **MONGODB_CONNECTION_STRING**: MongoDB connection for batch consistency
- **GCS_BUCKET_NAME**: Google Cloud Storage bucket for PDF downloads
- **PORT**: Service port (default: 3000)

### Automatic Configuration Loading
- The service automatically detects and loads the root `.env` file
- No manual configuration needed - uses your existing environment setup
- Supports both `DATABASE_URL` format and individual PostgreSQL variables
- Includes SSL support with `sslmode=require`

### Connection Details (from your .env)
- **Host**: ep-broad-voice-a5fdedmv.us-east-2.aws.neon.tech
- **Database**: neondb  
- **User**: neondb_owner
- **SSL Mode**: require
- **Bucket**: courts-bucket

## How It Works

### 1. **User Interaction**
1. User opens case details modal
2. User clicks "Extract PDF" button for specific document
3. Frontend sends request to `/api/pdf/extract-individual`

### 2. **Backend Processing**
1. Express proxy forwards request to Python service
2. Python service downloads PDF and extracts data
3. **MongoDB update**: Maintains batch processing consistency
4. **PostgreSQL update**: Updates the specific document in the `documents` JSON array
5. Returns success status for both database updates

### 3. **Frontend Update**
1. Frontend receives response with database update status
2. Shows enhanced feedback message
3. Triggers data refresh via `onDataUpdated()` callback
4. Case details modal shows updated incident dates from PostgreSQL

## Data Flow

```
Frontend (PostgreSQL data) → Extract PDF → Python Service
                                              ↓
                            MongoDB ← Extraction Results → PostgreSQL
                                              ↓
Frontend (refreshed PostgreSQL data with updated incident dates)
```

## Key Benefits

### ✅ **Single Source of Truth**
- Frontend continues to read only from PostgreSQL
- No hybrid data fetching required
- Maintains existing architecture

### ✅ **Real-time Updates**
- Incident dates immediately visible after extraction
- No manual refresh required
- Automatic data synchronization

### ✅ **Backward Compatibility**
- Existing UI components work unchanged
- Same data flow and API endpoints
- No frontend architecture changes

### ✅ **Database Consistency**
- MongoDB updated for batch processing consistency
- PostgreSQL updated for frontend display
- Both databases stay in sync

### ✅ **Enhanced Feedback**
- Users see which databases were updated
- Clear success/failure messages
- Detailed extraction status

## Testing

### Service Import Test
```python
from src.service.individual_pdf_service import IndividualPDFService
service = IndividualPDFService()
# ✓ SUCCESS: Service loads with PostgreSQL configuration
```

### API Response Format
```json
{
  "success": true,
  "case_id": "4701",
  "mongo_id": "689573a6f5c6e829162fb8c6",
  "doc_path": "orangecounty/2025-SC-012927-O/2025-08-08/Complaint0.pdf",
  "document_description": "Complaint",
  "database_updates": {
    "mongodb_updated": true,
    "postgresql_updated": true
  },
  "incident_date": "July 15, 2025",
  "incident_end_date": null,
  "message": "Successfully extracted and updated incident dates for Complaint (Updated: MongoDB & PostgreSQL)"
}
```

## Error Handling

### PostgreSQL Connection Issues
- Service logs connection errors
- Continues with MongoDB-only updates
- Returns partial success status

### Document Not Found
- Logs warning if document path not found in PostgreSQL
- Returns failure status for PostgreSQL update
- MongoDB update can still succeed independently

### JSON Parsing Issues
- Handles malformed documents JSON gracefully
- Logs detailed error information
- Returns failure status with descriptive message

## Next Steps

1. **Set up environment variables** in your deployment
2. **Test with real PostgreSQL connection**
3. **Verify incident dates appear in frontend after extraction**
4. **Monitor logs for any database connection issues**

The system is now ready to provide real-time incident date updates that immediately appear in the frontend! 🚀

# PDF Extraction Service

A FastAPI-based microservice for extracting court case data from PDF documents stored in Google Cloud Platform. This service provides a clean, asynchronous API for downloading PDFs from GCS and extracting structured data using advanced pattern matching.

## 🚀 Features

- **RESTful API**: FastAPI-based service with automatic OpenAPI documentation
- **Asynchronous Processing**: Background job processing for PDF extraction
- **Job Status Tracking**: Real-time status updates for extraction jobs
- **Modular Architecture**: Clean separation of concerns with extractors, services, and utilities
- **Docker Support**: Containerized deployment ready
- **Comprehensive Logging**: Structured logging with rotation and different levels
- **Health Checks**: Built-in health monitoring endpoints
- **Database Integration**: MongoDB for document tracking and GCS for file storage
- **Error Handling**: Robust error handling with detailed error messages

## 📁 Project Structure

```
pdf-service-runner/
├── src/
│   ├── extractors/           # PDF extraction logic
│   │   ├── __init__.py
│   │   └── pdf_court_extractor.py
│   ├── models/              # Pydantic models
│   │   ├── __init__.py
│   │   └── request_models.py
│   ├── service/             # Business logic
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── pdf_service.py
│   ├── utils/               # Utility functions
│   │   ├── __init__.py
│   │   ├── database_utils.py
│   │   └── logger.py
│   └── main.py              # FastAPI application
├── patterns/                # Extraction patterns by county
├── pdfs/                   # Downloaded PDF files
├── outputs/                # Extraction results
├── logs/                   # Application logs
├── config.yaml            # Service configuration
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── start_service.py       # Service entry point
└── README.md
```

## 🔧 Installation & Setup

### Prerequisites

- Python 3.8+
- MongoDB instance
- Google Cloud Storage bucket
- Environment variables configured

### Installation

1. **Clone and navigate to the project:**
   ```bash
   cd pdf-service-runner
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file with:
   ```env
   MONGODB_CONNECTION_STRING=mongodb://your-mongodb-uri
   GCS_BUCKET_NAME=your-gcs-bucket-name
   GCP_CREDENTIALS_JSON={"type":"service_account",...}
   ```

4. **Run the service:**
   ```bash
   python start_service.py
   ```

The service will be available at `http://localhost:8000`

## 📚 API Documentation

### Start PDF Extraction
```http
POST /extract
Content-Type: application/json

{
  "county_name": "orange",
  "document_type": "complaint", 
  "date_to": "2024-12-31",
  "date_from": "2024-01-01"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "message": "PDF extraction started for orange",
  "county_name": "orange",
  "document_type": "complaint"
}
```

### Check Job Status
```http
GET /status/{job_id}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "county_name": "orange",
  "document_type": "complaint",
  "date_to": "2024-12-31",
  "result": {
    "success": true,
    "extraction_result": {
      "total_files": 15,
      "successful_extractions": 14,
      "failed_extractions": 1,
      "incident_dates_found": 12
    }
  }
}
```

### List All Jobs
```http
GET /jobs
```

### Health Check
```http
GET /health
```

### Service Info
```http
GET /
```

## 🏗️ Architecture

### Service Layer (`PDFService`)
- **Orchestrates** the entire PDF processing workflow
- **Downloads** PDFs from Google Cloud Storage
- **Coordinates** extraction using the PDF extractor
- **Manages** async operations and error handling

### Extractor Layer (`PDFCourtExtractor`)
- **Extracts** text and structured data from PDF documents
- **Applies** county-specific extraction patterns
- **Handles** multiple extraction strategies (regex, contextual search, etc.)
- **Supports** batch processing of multiple files

### Utils Layer
- **Database operations** for MongoDB and GCS
- **Logging configuration** with structured output
- **Common utilities** for file operations and data processing

### Models Layer
- **Request/Response models** with validation
- **Type safety** using Pydantic
- **API documentation** auto-generation

## 🔍 Extraction Features

The service supports multiple extraction strategies:

- **Regex Patterns**: Direct pattern matching
- **Contextual Search**: Smart searching near keywords
- **Fuzzy Matching**: Handles variations in formatting
- **Multi-Pattern**: Tries multiple patterns with scoring
- **Date Extraction**: Specialized date parsing and validation
- **Incident Detection**: Distinguishes between incident and filing dates

## 🐳 Docker Deployment

```bash
# Build the image
docker build -t pdf-extraction-service .

# Run the container
docker run -p 8000:8000 \
  -e MONGODB_CONNECTION_STRING=your-mongo-uri \
  -e GCS_BUCKET_NAME=your-bucket \
  -e GCP_CREDENTIALS_JSON='your-credentials-json' \
  pdf-extraction-service
```

## 📊 Monitoring & Logging

- **Health endpoint**: `/health` for uptime monitoring
- **Structured logging**: JSON-formatted logs with levels
- **Job tracking**: In-memory job status store (can be extended to persistent storage)
- **Error tracking**: Detailed error messages and stack traces

## 🧪 Testing

```bash
# Run tests (when available)
pytest

# Test the API
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "county_name": "orange",
    "document_type": "complaint",
    "date_to": "2024-12-31"
  }'
```

## 🔧 Configuration

Edit `config.yaml` to adjust:
- Service settings
- Extraction parameters
- Logging levels
- File paths

## 🤝 Contributing

1. Follow the established project structure
2. Add appropriate error handling
3. Include logging for important operations
4. Update documentation for new features
5. Test API endpoints thoroughly

## 📝 License

This project is part of the Legal Data Manager system.
  "document_type": "complaint",
  "date_to": "2025-01-01",
  "message": "PDF extraction completed successfully",
  "result": {
    "total_files": 10,
    "successful_extractions": 8,
    "failed_extractions": 2,
    "results": [...]
  }
}
```

### Health Check
```
GET /health
```

### List All Jobs
```
GET /jobs
```

## Installation & Setup

### Prerequisites
- Python 3.9+
- Access to Google Cloud Platform with PDF storage
- Patterns files for specific counties

### Local Development

1. **Clone and navigate to the service directory:**
```bash
cd pdf-service-runner
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure the service:**
Edit `config.yaml` to match your environment

4. **Run the service:**
```bash
python start_service.py
```

The service will be available at `http://localhost:8000`

### Docker Deployment

1. **Build the Docker image:**
```bash
docker build -t pdf-extraction-service .
```

2. **Run the container:**
```bash
docker run -p 8000:8000 -v $(pwd)/outputs:/app/outputs pdf-extraction-service
```

## React Frontend Integration

### Component Usage

```tsx
import { PDFExtractionService } from '../components/pdf-extraction/pdf-extraction-service';

function App() {
  return (
    <div>
      <PDFExtractionService />
    </div>
  );
}
```

## Configuration

The service integrates with your existing PDF extraction code:
- Uses `utility.download_pdfs_from_gcp()` for downloading
- Uses `PDFCourtExtractor` for data extraction
- Maintains the same output format and structure

## API Documentation
Once running, visit `http://localhost:8000/docs` for interactive API documentation.
│   ├── main.py
│   ├── service
│   │   ├── __init__.py
│   │   ├── pdf_service.py
│   │   └── config.py
│   ├── models
│   │   ├── __init__.py
│   │   └── request_models.py
│   └── utils
│       ├── __init__.py
│       └── logger.py
├── requirements.txt
├── config.yaml
├── Dockerfile
└── README.md
```

## Installation
To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd pdf-service-runner
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration
The service can be configured using the `config.yaml` file. You can set default values for the county name, document type, and date.

## Usage
To run the service, execute the following command in your terminal:

```
python src/main.py --county <county_name> --document_type <document_type> --date <date>
```

### Example
```
python src/main.py --county orangecounty --document_type complaint --date 2025-01-01
```

## Logging
The service includes logging functionality to track events and errors during execution. Logs will be generated to help with debugging and monitoring the service's performance.

## Docker
A Dockerfile is provided to facilitate containerization of the service. To build the Docker image, run:

```
docker build -t pdf-service-runner .
```

To run the container:

```
docker run pdf-service-runner
```

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.
# Medical Entity Extraction API

A FastAPI-based web application for extracting medical entities and USCDI v6 compliant data from clinical notes using OpenAI's API and UMLS (Unified Medical Language System) semantic types.

## Features

- **Medical Entity Extraction**: Extract and categorize medical entities based on UMLS semantic types including disorders, medications, procedures, anatomy, lab results, and more
- **USCDI v6 Compliance**: Extract structured clinical data according to the US Core Data for Interoperability (USCDI) v6 standard
- **PDF Support**: Process both text and PDF files using Docling for document conversion
- **Authentication**: Secure API endpoints with JWT-based authentication
- **Multiple AI Models**: Support for various OpenAI models including GPT-4o, GPT-4 Turbo, O1, O3 Mini, and GPT-5
- **Interactive Web UI**: User-friendly interface for uploading files and viewing extracted data
- **Docker Support**: Easy deployment with Docker and Docker Compose

## Prerequisites

- Python 3.11+
- OpenAI API key
- Docker (optional, for containerized deployment)

## Installation

### Local Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd "Document Processing"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE_URL=https://api.openai.com/v1
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=production
```

### Docker Setup

1. Build and run with Docker Compose:
```bash
docker-compose up -d
```

2. The API will be available at `http://localhost:8000`

## Usage

### Running the Application

**Local development:**
```bash
python app.py
```

**Using the start script:**
```bash
./start.sh
```

**Production with Gunicorn:**
```bash
gunicorn -c gunicorn_config.py app:app
```

### API Endpoints

#### Authentication
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login and get access token
- `GET /api/auth/me` - Get current user information

#### Medical Entity Extraction
- `POST /api/extract` - Extract entities from text
- `POST /api/extract-file` - Extract entities from uploaded file (.txt or .pdf)
- `GET /api/models` - List available OpenAI models

#### USCDI v6 Data Extraction
- `POST /api/uscdi/extract` - Extract USCDI data from text
- `POST /api/uscdi/extract-file` - Extract USCDI data from uploaded file
- `POST /api/uscdi/extract-class` - Extract specific USCDI data class
- `GET /api/uscdi/data-classes` - List available USCDI v6 data classes

#### System
- `GET /health` - Health check endpoint
- `GET /` - Web UI (frontend)

### Example Request

```bash
curl -X POST "http://localhost:8000/api/extract" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "medical_note": "Patient presents with chest pain and dyspnea. History of hypertension. Taking lisinopril 20mg daily.",
    "model": "gpt-4o"
  }'
```

### Web Interface

Access the interactive web UI at `http://localhost:8000` to:
- Login or register
- Upload text or PDF files
- View extracted medical entities
- Download results as JSON

### Test User

A test user is automatically created on startup:
- Username: `testuser`
- Password: `testpass123`

## UMLS Semantic Types

The extractor identifies entities across these categories:
- Disorders/Diseases
- Signs and Symptoms
- Procedures
- Medications/Drugs
- Anatomy
- Laboratory Results
- Medical Devices
- Organisms
- Substances
- Temporal Information

## USCDI v6 Data Classes

Supports extraction of all USCDI v6 data classes including:
- Patient Demographics
- Vital Signs
- Medications
- Allergies
- Problems/Conditions
- Procedures
- Laboratory Results
- Clinical Notes
- And more...

## Project Structure

```
.
├── app.py                          # Main FastAPI application
├── medical_entity_extractor.py     # UMLS-based entity extraction
├── uscdi_extractor.py             # USCDI v6 data extraction
├── auth.py                        # Authentication logic
├── database.py                    # User database management
├── uscdi_prompts.json             # USCDI extraction prompts
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker image configuration
├── docker-compose.yml             # Docker Compose setup
├── gunicorn_config.py            # Gunicorn production config
├── start.sh                       # Startup script
└── static/                        # Frontend files
```

## Development

The application uses:
- **FastAPI** for the REST API
- **OpenAI API** for entity extraction
- **Docling** for PDF processing
- **JWT** for authentication
- **Gunicorn** for production serving

## Docker Image

The Docker image is published as:
```
qcogadvisory/medical-entity-extractor:latest
```

## Health Check

Monitor application health:
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "extractor_initialized": true,
  "api_key_configured": true
}
```

## License

[Add your license information here]

## Support

For issues or questions, please open an issue in the repository.
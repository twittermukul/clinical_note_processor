"""
FastAPI application for medical entity extraction using UMLS and OpenAI API
"""

from fastapi import FastAPI, HTTPException, File, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import timedelta
import logging
import os
from pathlib import Path
import tempfile

from medical_entity_extractor import MedicalEntityExtractor
from uscdi_extractor import USCDIExtractor

# Import docling for PDF processing
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logger.warning("Docling not available. PDF support will be disabled.")
from auth import (
    Token, UserCreate, UserLogin, User,
    create_access_token, get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from database import create_user, authenticate_user, get_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Medical Entity Extraction API",
    description="Extract UMLS-based medical entities from clinical notes using OpenAI",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend)
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Initialize extractors
try:
    extractor = MedicalEntityExtractor()
    logger.info("Medical entity extractor initialized successfully")
except ValueError as e:
    logger.error(f"Failed to initialize extractor: {e}")
    extractor = None

try:
    uscdi_extractor = USCDIExtractor()
    logger.info("USCDI extractor initialized successfully")
except ValueError as e:
    logger.error(f"Failed to initialize USCDI extractor: {e}")
    uscdi_extractor = None

# Initialize database with test user
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    from database import users_db, create_user

    if "testuser" not in users_db:
        try:
            create_user("testuser", "test@example.com", "testpass123")
            logger.info("Test user created: testuser / testpass123")
        except Exception as e:
            logger.error(f"Failed to create test user: {e}")


# Pydantic models
class ExtractionRequest(BaseModel):
    medical_note: str
    model: Optional[str] = "gpt-4o"

    class Config:
        json_schema_extra = {
            "example": {
                "medical_note": "Patient presents with chest pain and dyspnea. History of hypertension. Taking lisinopril 20mg daily.",
                "model": "gpt-4o"
            }
        }


class ExtractionResponse(BaseModel):
    success: bool
    entities: Optional[Dict] = None
    error: Optional[str] = None
    total_entities: Optional[int] = None
    original_text: Optional[str] = None


class USCDIExtractionResponse(BaseModel):
    success: bool
    uscdi_data: Optional[Dict] = None
    error: Optional[str] = None
    data_classes_count: Optional[int] = None
    original_text: Optional[str] = None


# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main frontend page"""
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Medical Entity Extraction API</h1><p>Frontend not found. Please ensure static/index.html exists.</p>"
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "extractor_initialized": extractor is not None,
        "api_key_configured": bool(os.getenv("OPENAI_API_KEY"))
    }


@app.post("/api/extract", response_model=ExtractionResponse)
async def extract_entities(
    request: ExtractionRequest,
    current_user: str = Depends(get_current_active_user)
):
    """
    Extract medical entities from a clinical note (Protected endpoint - requires authentication)

    - **medical_note**: The clinical note text
    - **model**: OpenAI model to use (default: gpt-4o)
    """
    if not extractor:
        raise HTTPException(
            status_code=500,
            detail="Extractor not initialized. Please check OPENAI_API_KEY environment variable."
        )

    if not request.medical_note or not request.medical_note.strip():
        raise HTTPException(
            status_code=400,
            detail="Medical note text is required and cannot be empty"
        )

    try:
        logger.info(f"Processing extraction request with model: {request.model}")
        entities = extractor.extract_entities(request.medical_note, model=request.model)

        # Calculate total entities
        total_entities = sum(
            len(v) if isinstance(v, list) else 0
            for v in entities.values()
        )

        logger.info(f"Successfully extracted {total_entities} entities")

        return ExtractionResponse(
            success=True,
            entities=entities,
            total_entities=total_entities
        )

    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting entities: {str(e)}"
        )


@app.post("/api/extract-file")
async def extract_from_file(
    file: UploadFile = File(...),
    model: str = "gpt-4o",
    current_user: str = Depends(get_current_active_user)
):
    """
    Extract medical entities from an uploaded text file (Protected endpoint - requires authentication)

    - **file**: Text file containing clinical note
    - **model**: OpenAI model to use (default: gpt-4o)
    """
    if not extractor:
        raise HTTPException(
            status_code=500,
            detail="Extractor not initialized. Please check OPENAI_API_KEY environment variable."
        )

    # Validate file type
    if not file.filename.endswith(('.txt', '.text', '.pdf')):
        raise HTTPException(
            status_code=400,
            detail="Only .txt, .text, and .pdf files are supported"
        )

    try:
        # Read file content
        if file.filename.endswith('.pdf'):
            if not DOCLING_AVAILABLE:
                raise HTTPException(
                    status_code=400,
                    detail="PDF support not available. Please install docling."
                )

            # Save uploaded PDF to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_path = tmp_file.name

            try:
                # Convert PDF to text using docling
                converter = DocumentConverter()
                result = converter.convert(tmp_path)
                medical_note = result.document.export_to_markdown()
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
        else:
            # Handle text files
            content = await file.read()
            medical_note = content.decode('utf-8')

        if not medical_note.strip():
            raise HTTPException(
                status_code=400,
                detail="File is empty"
            )

        logger.info(f"Processing file upload: {file.filename}")
        entities = extractor.extract_entities(medical_note, model=model)

        total_entities = sum(
            len(v) if isinstance(v, list) else 0
            for v in entities.values()
        )

        logger.info(f"Successfully extracted {total_entities} entities from file")

        return ExtractionResponse(
            success=True,
            entities=entities,
            total_entities=total_entities,
            original_text=medical_note
        )

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be valid UTF-8 encoded text"
        )
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting entities: {str(e)}"
        )


@app.post("/api/uscdi/extract-file")
async def extract_uscdi_from_file(
    file: UploadFile = File(...),
    model: str = "gpt-4o",
    current_user: str = Depends(get_current_active_user)
):
    """
    Extract USCDI v6 data from an uploaded file (Protected endpoint - requires authentication)

    - **file**: Text or PDF file containing clinical note
    - **model**: OpenAI model to use (default: gpt-4o)
    """
    if not uscdi_extractor:
        raise HTTPException(
            status_code=500,
            detail="USCDI extractor not initialized. Please check OPENAI_API_KEY environment variable."
        )

    # Validate file type
    if not file.filename.endswith(('.txt', '.text', '.pdf')):
        raise HTTPException(
            status_code=400,
            detail="Only .txt, .text, and .pdf files are supported"
        )

    try:
        # Read file content
        if file.filename.endswith('.pdf'):
            if not DOCLING_AVAILABLE:
                raise HTTPException(
                    status_code=400,
                    detail="PDF support not available. Please install docling."
                )

            # Save uploaded PDF to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_path = tmp_file.name

            try:
                # Convert PDF to text using docling
                converter = DocumentConverter()
                result = converter.convert(tmp_path)
                medical_note = result.document.export_to_markdown()
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
        else:
            # Handle text files
            content = await file.read()
            medical_note = content.decode('utf-8')

        if not medical_note.strip():
            raise HTTPException(
                status_code=400,
                detail="File is empty"
            )

        logger.info(f"Processing USCDI extraction from file: {file.filename} (parallel mode with UMLS)")
        uscdi_data = uscdi_extractor.extract_uscdi_data_parallel(medical_note, model=model, add_umls_cui=True)

        # Count non-empty data classes (excluding _metadata)
        data_classes_count = sum(
            1 for k, v in uscdi_data.items()
            if not k.startswith('_') and v and (
                (isinstance(v, list) and len(v) > 0) or
                (isinstance(v, dict) and len(v) > 0) or
                (isinstance(v, str) and v.strip())
            )
        )

        logger.info(f"Successfully extracted {data_classes_count} USCDI data classes from file with UMLS enrichment")

        return USCDIExtractionResponse(
            success=True,
            uscdi_data=uscdi_data,
            data_classes_count=data_classes_count,
            original_text=medical_note
        )

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be valid UTF-8 encoded text"
        )
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting USCDI data: {str(e)}"
        )


@app.get("/api/models")
async def list_models():
    """List available OpenAI models for extraction"""
    return {
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o (Recommended)", "description": "Most capable model"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "Faster and more cost-effective"},
            {"id": "o1", "name": "O1", "description": "Advanced reasoning model"},
            {"id": "o1-mini", "name": "O1 Mini", "description": "Fast reasoning model"},
            {"id": "o3-mini", "name": "O3 Mini", "description": "Latest reasoning model"},
            {"id": "gpt-5", "name": "GPT-5", "description": "Next generation model"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "High capability"},
            {"id": "gpt-4", "name": "GPT-4", "description": "Powerful language model"},
        ]
    }


# Authentication endpoints
@app.post("/api/auth/register", response_model=User)
async def register(user_data: UserCreate):
    """Register a new user"""
    try:
        user = create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        logger.info(f"New user registered: {user.username}")
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    logger.info(f"User logged in: {user.username}")

    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/auth/me", response_model=User)
async def read_users_me(current_user: str = Depends(get_current_active_user)):
    """Get current user information"""
    user = get_user(current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# USCDI v6 endpoints
@app.post("/api/uscdi/extract")
async def extract_uscdi_data(
    request: ExtractionRequest,
    current_user: str = Depends(get_current_active_user)
):
    """
    Extract USCDI v6 compliant structured data from clinical note (Protected endpoint)

    - **medical_note**: The clinical note text
    - **model**: OpenAI model to use (default: gpt-4o)
    """
    if not uscdi_extractor:
        raise HTTPException(
            status_code=500,
            detail="USCDI extractor not initialized. Please check OPENAI_API_KEY environment variable."
        )

    if not request.medical_note or not request.medical_note.strip():
        raise HTTPException(
            status_code=400,
            detail="Medical note text is required and cannot be empty"
        )

    try:
        logger.info(f"Processing USCDI extraction request with model: {request.model} (parallel mode with UMLS)")
        uscdi_data = uscdi_extractor.extract_uscdi_data_parallel(request.medical_note, model=request.model, add_umls_cui=True)

        # Count data classes extracted
        data_classes_count = len([k for k in uscdi_data.keys() if not k.startswith('_')])

        logger.info(f"Successfully extracted {data_classes_count} USCDI data classes with UMLS enrichment")

        return {
            "success": True,
            "uscdi_data": uscdi_data,
            "data_classes_count": data_classes_count
        }

    except Exception as e:
        logger.error(f"Error during USCDI extraction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting USCDI data: {str(e)}"
        )


@app.post("/api/uscdi/extract-class")
async def extract_uscdi_class(
    request: ExtractionRequest,
    data_class: str,
    current_user: str = Depends(get_current_active_user)
):
    """
    Extract specific USCDI data class from clinical note (Protected endpoint)

    - **medical_note**: The clinical note text
    - **data_class**: USCDI data class to extract (e.g., 'medications', 'vital_signs')
    - **model**: OpenAI model to use (default: gpt-4o)
    """
    if not uscdi_extractor:
        raise HTTPException(
            status_code=500,
            detail="USCDI extractor not initialized."
        )

    if not request.medical_note or not request.medical_note.strip():
        raise HTTPException(
            status_code=400,
            detail="Medical note text is required and cannot be empty"
        )

    try:
        logger.info(f"Extracting USCDI data class: {data_class}")
        class_data = uscdi_extractor.extract_specific_class(
            request.medical_note,
            data_class,
            model=request.model
        )

        return {
            "success": True,
            "data_class": data_class,
            "data": class_data
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error extracting USCDI class {data_class}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting USCDI data class: {str(e)}"
        )


@app.get("/api/uscdi/data-classes")
async def get_uscdi_data_classes(current_user: str = Depends(get_current_active_user)):
    """Get list of available USCDI v6 data classes"""
    if not uscdi_extractor:
        raise HTTPException(
            status_code=500,
            detail="USCDI extractor not initialized."
        )

    data_classes = uscdi_extractor.get_available_data_classes()

    return {
        "uscdi_version": "v6",
        "data_classes": data_classes,
        "total_classes": len(data_classes)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

# Multi-stage build for Medical Entity Extraction API

# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser medical_entity_extractor.py .
COPY --chown=appuser:appuser uscdi_extractor.py .
COPY --chown=appuser:appuser uscdi_prompts.json .
COPY --chown=appuser:appuser auth.py .
COPY --chown=appuser:appuser database.py .
COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser gunicorn_config.py .
COPY --chown=appuser:appuser static/ ./static/

# Set PATH to include user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run with gunicorn
CMD ["gunicorn", "app:app", "-c", "gunicorn_config.py"]

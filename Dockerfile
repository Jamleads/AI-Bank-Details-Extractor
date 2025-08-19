# Multi-stage build for AI Bank Details Extractor
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads output logs && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/appuser/.local/bin:$PATH

# Cloud Run expects the app to listen on port 8080
ENV HOST=0.0.0.0
ENV PORT=8080

# Production settings
ENV PRODUCTION=true

# GCP-specific environment variables
ENV CLOUD=GCP
ENV DATABASE_TYPE=firestore
ENV USE_GCS_STORAGE=true
ENV USE_GCP_SECRETS=true

# Switch to non-root user
USER appuser

# Expose the port that Cloud Run expects
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Start the application
CMD ["python", "main.py"]

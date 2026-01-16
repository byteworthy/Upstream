# Dockerfile for Payrixa Django Application
# Multi-stage build for optimized production images

# Stage 1: Base image with Python dependencies
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage 2: Development image
FROM base as development

# Copy application code
COPY . /app/

# Create directories
RUN mkdir -p /app/logs /app/reports /app/hello_world/staticfiles /app/hello_world/media

# Expose port
EXPOSE 8000

# Default command for development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Stage 3: Production image
FROM base as production

# Create non-root user
RUN useradd -m -u 1000 payrixa && \
    mkdir -p /app/logs /app/reports /app/hello_world/staticfiles /app/hello_world/media && \
    chown -R payrixa:payrixa /app

# Copy application code
COPY --chown=payrixa:payrixa . /app/

# Switch to non-root user
USER payrixa

# Collect static files (can be overridden)
RUN python manage.py collectstatic --noinput --clear || true

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/health/', timeout=5)" || exit 1

# Default command for production (use gunicorn)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "hello_world.wsgi:application"]

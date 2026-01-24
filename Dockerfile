# Dockerfile for Upstream Django Application
# Optimized for Google Cloud Run deployment

FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=upstream.settings.prod \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    libpq-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies including Gunicorn
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/reports /app/hello_world/staticfiles /app/hello_world/media && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Collect static files
RUN python manage.py collectstatic --no-input --settings=upstream.settings.prod || true

# Expose port (Cloud Run uses PORT env var, default 8080)
EXPOSE 8080

# Start Gunicorn (Cloud Run provides PORT env var)
CMD exec gunicorn hello_world.wsgi:application \
    --bind :$PORT \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info

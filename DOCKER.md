# Docker Setup for Upstream

This document explains how to run Upstream using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

## Quick Start

### 1. Build and Start Services

```bash
# Start all services (web, postgres, redis)
docker-compose up -d

# View logs
docker-compose logs -f web
```

### 2. Run Migrations

```bash
docker-compose exec web python manage.py migrate
```

### 3. Create Superuser (Optional)

```bash
docker-compose exec web python manage.py createsuperuser
```

### 4. Access the Application

- Web Application: http://localhost:8000
- Admin Interface: http://localhost:8000/admin/
- API: http://localhost:8000/api/v1/
- API Documentation: http://localhost:8000/api/v1/docs/

## Docker Services

### Web Service
- Django application server
- Port: 8000
- Depends on: PostgreSQL, Redis

### Database Service (PostgreSQL)
- PostgreSQL 15
- Port: 5432
- Data persisted in `postgres_data` volume

### Redis Service
- Redis 7 (for Celery in future chunks)
- Port: 6379
- Data persisted in `redis_data` volume

## Common Commands

### Development Workflow

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart a service
docker-compose restart web

# View logs
docker-compose logs -f web
docker-compose logs -f db

# Shell access
docker-compose exec web bash
docker-compose exec web python manage.py shell

# Database shell
docker-compose exec db psql -U upstream -d upstream
```

### Running Management Commands

```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create migrations
docker-compose exec web python manage.py makemigrations

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Load fixtures
docker-compose exec web python manage.py loaddata upstream/fixtures/demo_data.json

# Run drift detection
docker-compose exec web python manage.py run_weekly_payer_drift --customer-id=1

# Send alerts
docker-compose exec web python manage.py send_alerts

# Generate report artifacts
docker-compose exec web python manage.py generate_report_artifacts
```

### Running Tests

```bash
# Run all tests
docker-compose exec web python manage.py test

# Run specific test module
docker-compose exec web python manage.py test payrixa.tests_api

# Run with verbosity
docker-compose exec web python manage.py test --verbosity=2

# Run checks
docker-compose exec web python manage.py check
```

## Environment Variables

Create a `.env` file in the project root to override defaults:

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here

# Database Settings
DB_NAME=upstream
DB_USER=upstream
DB_PASSWORD=secure_password_here
DB_HOST=db
DB_PORT=5432

# Redis Settings
REDIS_URL=redis://redis:6379/0

# Email Settings
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=alerts@upstream.cx
```

## Production Deployment

### Build Production Image

```bash
# Build production image
docker build --target production -t upstream:latest .

# Run production container
docker run -d \
  -p 8000:8000 \
  -e DEBUG=False \
  -e SECRET_KEY=your-secret-key \
  -e DB_HOST=your-db-host \
  -e DB_PASSWORD=your-db-password \
  upstream:latest
```

### Production Considerations

1. **Use PostgreSQL** - The production setup should use a managed PostgreSQL instance
2. **Set DEBUG=False** - Always disable debug mode in production
3. **Use gunicorn** - The production Dockerfile uses gunicorn (4 workers by default)
4. **Static Files** - Run `collectstatic` and serve via CDN/nginx
5. **Environment Variables** - Use secrets management (AWS Secrets Manager, etc.)
6. **Health Checks** - The Dockerfile includes health checks for orchestration
7. **Non-root User** - Production image runs as non-root user `upstream`

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000

# Or use a different port
docker-compose up -d
docker-compose exec web python manage.py runserver 0.0.0.0:8001
```

### Database Connection Issues

```bash
# Check database is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Permission Issues

```bash
# If you have permission issues with volumes
docker-compose down -v
docker-compose up -d
```

### Reset Everything

```bash
# Stop and remove all containers and volumes
docker-compose down -v

# Rebuild and start fresh
docker-compose up --build -d
docker-compose exec web python manage.py migrate
```

## Volume Management

### Backup Database

```bash
# Backup PostgreSQL data
docker-compose exec db pg_dump -U upstream upstream > backup.sql

# Restore from backup
docker-compose exec -T db psql -U upstream upstream < backup.sql
```

### Clean Up Volumes

```bash
# Remove all volumes (WARNING: destroys data)
docker-compose down -v

# Remove specific volume
docker volume rm codespaces-django_postgres_data
```

## Integration with Existing Workflow

Docker is **optional**. The existing non-Docker development workflow continues to work:

```bash
# Traditional development (still supported)
python manage.py runserver
python manage.py test
```

Docker provides:
- Consistent development environment
- Easy PostgreSQL setup
- Redis for Celery (Chunk 10)
- CI/CD integration (Chunk 9)
- Production parity

## Next Steps

- **Chunk 9**: GitHub Actions CI will use Docker for testing
- **Chunk 10**: Celery workers will run as additional Docker services
- **Chunk 11**: Monitoring stack (Prometheus/Grafana) via Docker Compose

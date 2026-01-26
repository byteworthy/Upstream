from django.apps import AppConfig
from django.conf import settings
from pathlib import Path


class UpstreamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "upstream"

    def ready(self):
        """
        Security checks on application startup.

        Validates .env file permissions to prevent exposure of sensitive
        credentials (FIELD_ENCRYPTION_KEY, SECRET_KEY, DB_PASSWORD).
        """
        from upstream.env_permissions import check_env_permissions

        # Get path to .env file (project root)
        env_file = Path(__file__).resolve().parent.parent / ".env"

        # Strict mode in production (DEBUG=False), warn-only in development
        strict = not settings.DEBUG

        # Validate permissions (skips if .env doesn't exist or in CI)
        check_env_permissions(env_file, strict=strict)

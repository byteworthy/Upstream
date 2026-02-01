from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "upstream.billing"

    def ready(self):
        # Import signals to register them
        import upstream.billing.signals  # noqa: F401

from django.apps import AppConfig


class IaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # type: ignore
    name = "apps.ia"
    verbose_name = "IA (LLM local)"

from django.apps import AppConfig


class AlertasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.alertas'

    def ready(self):
        import apps.alertas.signals  # 🔽 registra la signal
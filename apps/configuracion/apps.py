from django.apps import AppConfig

class ConfiguracionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.configuracion'
    
    def ready(self):
        from . import signals  # noqa
from django.apps import AppConfig


class SaritasappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'saritasapp'
    
    def ready(self):
        from .models import ItemType
        ItemType.initialize_choices()
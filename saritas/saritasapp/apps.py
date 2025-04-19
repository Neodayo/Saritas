from django.apps import AppConfig


class SaritasappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'saritasapp'
    
    def ready(self):
        """Populate ItemType when Django starts"""
        from .models import ItemType
        for code, name in ItemType.ITEM_TYPES:
            ItemType.objects.get_or_create(name=code)
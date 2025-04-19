from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import ItemType

@receiver(post_migrate)
def populate_itemtypes(sender, **kwargs):
    if sender.name == 'saritasapp':
        ItemType.initialize()  # Make sure this matches your model method name
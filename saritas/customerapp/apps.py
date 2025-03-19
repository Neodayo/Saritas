from django.apps import AppConfig
from django.db.models.signals import post_migrate

class CustomerappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customerapp'

    def ready(self):
        post_migrate.connect(create_customer_group, sender=self)

def create_customer_group(sender, **kwargs):
    from django.contrib.auth.models import Group  # ✅ Moved import here
    Group.objects.get_or_create(name='Customers')

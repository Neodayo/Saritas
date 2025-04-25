from django import template
from saritasapp.utils.encryption import encrypt_id

register = template.Library()

@register.filter
def encrypt(value):
    """Template filter to encrypt IDs"""
    try:
        return encrypt_id(value)
    except Exception:
        return str(value)  # Fallback to raw ID
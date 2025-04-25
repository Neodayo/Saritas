# encryption_tags.py
from django import template
from core.utils.encryption import encrypt_id

register = template.Library()

@register.filter
def encrypt(value):
    """Universal encryption filter for both apps"""
    try:
        return encrypt_id(value)
    except Exception:
        return str(value)  # Fallback
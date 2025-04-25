# core/converters.py
from django.urls.converters import StringConverter
from core.utils.encryption import decrypt_id

class EncryptedIDConverter(StringConverter):
    regex = r'[\w\-]+'
    
    def to_python(self, value):
        try:
            return decrypt_id(value)
        except ValueError:
            raise ValueError("Invalid encrypted ID")
    
    def to_url(self, value):
        from core.utils.encryption import encrypt_id
        return encrypt_id(value)
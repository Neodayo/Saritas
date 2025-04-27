from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import logging
from django.core.exceptions import BadRequest
from django.http import Http404

logger = logging.getLogger(__name__)

class EncryptionService:
    """Central encryption service for all apps"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize with key from settings"""
        if not hasattr(settings, 'FERNET_KEY'):
            logger.critical("FERNET_KEY missing in settings!")
            raise RuntimeError("Encryption key not configured")
        
        try:
            self.fernet = Fernet(settings.FERNET_KEY.encode())
        except Exception as e:
            logger.critical(f"Encryption setup failed: {str(e)}")
            raise

    def encrypt(self, data):
        """Encrypt any string data"""
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise ValueError("Encryption failed")

    def decrypt(self, encrypted_data):
        """Decrypt encrypted data"""
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except InvalidToken:
            logger.warning("Invalid token - possible tampering")
            raise ValueError("Invalid encrypted data")
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise ValueError("Decryption failed")

    def encrypt_id(self, id_value):
        """Specialized method for ID encryption (URL-safe)"""
        try:
            encrypted = self.fernet.encrypt(str(id_value).encode())
            return base64.urlsafe_b64encode(encrypted).decode().rstrip('=')
        except Exception as e:
            logger.error(f"ID encryption failed: {str(e)}")
            raise ValueError("ID encryption failed")

    def decrypt_id(self, encrypted_id):
        """Specialized method for ID decryption"""
        try:
            # Add padding if needed
            pad_length = len(encrypted_id) % 4
            if pad_length:
                encrypted_id += '=' * (4 - pad_length)
            
            decrypted = self.fernet.decrypt(
                base64.urlsafe_b64decode(encrypted_id.encode())
            )
            return int(decrypted.decode())
        except Exception as e:
            logger.error(f"ID decryption failed: {str(e)}")
            raise ValueError("Invalid encrypted ID")

# Initialize service
encryption_service = EncryptionService()

# Convenience functions
def encrypt_id(id_value):
    """Shortcut for ID encryption"""
    return encryption_service.encrypt_id(id_value)

def decrypt_id(encrypted_id):
    """Shortcut for ID decryption"""
    return encryption_service.decrypt_id(encrypted_id)

def get_decrypted_object_or_404(model, identifier):
    """Safe object retrieval that can handle both encrypted and plain IDs"""
    try:
        # First try to treat as plain ID
        try:
            obj_id = int(identifier)
            return model.objects.get(pk=obj_id)
        except (ValueError, TypeError):
            # If that fails, try to decrypt
            obj_id = decrypt_id(identifier)
            return model.objects.get(pk=obj_id)
    except ValueError as e:
        logger.warning(f"Invalid ID format: {identifier}")
        raise BadRequest("Invalid identifier format")
    except model.DoesNotExist:
        logger.warning(f"Object not found for ID: {identifier}")
        raise Http404(f"{model.__name__} not found")
    
# Add this at the bottom of your encryption.py
def model_to_encrypted_dict(instance):
    """Convert model instance to dict with encrypted ID"""
    from django.forms.models import model_to_dict
    data = model_to_dict(instance)
    data['encrypted_id'] = encrypt_id(instance.pk)
    return data
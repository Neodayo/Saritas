from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
import base64
import logging
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404

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

    def encrypt_id(self, id_value):
        """Specialized method for ID encryption (URL-safe)"""
        try:
            encrypted = self.fernet.encrypt(str(id_value).encode())
            return base64.urlsafe_b64encode(encrypted).decode().rstrip('=')
        except Exception as e:
            logger.error(f"ID encryption failed: {str(e)}")
            return str(id_value)  # Fallback to plain ID

    def decrypt_id(self, encrypted_id):
        """Specialized method for ID decryption"""
        try:
            # If already a number
            if isinstance(encrypted_id, int):
                return encrypted_id
                
            # If numeric string
            if encrypted_id.isdigit():
                return int(encrypted_id)
            
            # Handle encrypted strings
            padding = len(encrypted_id) % 4
            if padding:
                encrypted_id += '=' * (4 - padding)
                
            decrypted = self.fernet.decrypt(
                base64.urlsafe_b64decode(encrypted_id.encode())
            )
            return int(decrypted.decode())
        except Exception as e:
            logger.error(f"ID decryption failed: {str(e)}")
            raise ValidationError("Invalid encrypted ID")

# Initialize service
encryption_service = EncryptionService()

# Public interface functions
def encrypt_id(pk):
    """Public interface for ID encryption"""
    return encryption_service.encrypt_id(pk)

def decrypt_id(encrypted_id):
    """Public interface for ID decryption"""
    return encryption_service.decrypt_id(encrypted_id)

def get_decrypted_object_or_404(model, encrypted_id, queryset=None):
    """
    Get object by decrypted ID or raise 404
    Handles both encrypted and numeric IDs
    """
    try:
        # First try to decrypt as encrypted ID
        try:
            obj_id = decrypt_id(encrypted_id)
            if queryset is not None:
                return queryset.get(pk=obj_id)
            return model.objects.get(pk=obj_id)
        except ValidationError:
            # Fall back to numeric ID if decryption fails
            if encrypted_id.isdigit():
                obj_id = int(encrypted_id)
                if queryset is not None:
                    return queryset.get(pk=obj_id)
                return model.objects.get(pk=obj_id)
            raise Http404("Invalid object identifier")
    except model.DoesNotExist:
        raise Http404("Object not found")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise Http404("Error retrieving object")
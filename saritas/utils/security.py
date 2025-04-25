from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import logging
from django.core.exceptions import BadRequest
from django.http import Http404

logger = logging.getLogger(__name__)

class EncryptionService:
    """Singleton service for handling encryption/decryption"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize encryption service with proper key handling"""
        if not hasattr(settings, 'FERNET_KEY'):
            logger.warning("Using default FERNET_KEY - not recommended for production!")
            settings.FERNET_KEY = 'XEg3_OYMjtDBh0esyy5lajk7WvX3RCTkIK67-IAjGEU='
        
        try:
            self.fernet = Fernet(settings.FERNET_KEY.encode())
        except Exception as e:
            logger.critical(f"Encryption setup failed: {str(e)}")
            raise RuntimeError("Failed to initialize encryption service")

    def encrypt_id(self, id):
        """Encrypts an integer ID to URL-safe string with proper padding"""
        try:
            encrypted = self.fernet.encrypt(str(id).encode())
            # Ensure proper URL-safe base64 encoding
            return base64.urlsafe_b64encode(encrypted).decode().rstrip('=')
        except Exception as e:
            logger.error(f"Encryption failed for ID {id}: {str(e)}")
            raise ValueError("Failed to encrypt ID")

    def decrypt_id(self, encrypted_id):
        """Decrypts an encrypted string back to integer ID with padding handling"""
        try:
            # Add padding if needed (base64 requires length divisible by 4)
            padding = len(encrypted_id) % 4
            if padding:
                encrypted_id += '=' * (4 - padding)
            
            decrypted = self.fernet.decrypt(
                base64.urlsafe_b64decode(encrypted_id.encode())
            )
            return int(decrypted.decode())
        except InvalidToken:
            logger.error("Invalid token during decryption - possible tampering")
            raise ValueError("Invalid encrypted ID")
        except Exception as e:
            logger.error(f"Decryption failed for {encrypted_id}: {str(e)}")
            raise ValueError("Failed to decrypt ID")

# Initialize the service
encryption_service = EncryptionService()

# Helper functions for convenience
def encrypt_id(id):
    return encryption_service.encrypt_id(id)

def decrypt_id(encrypted_id):
    return encryption_service.decrypt_id(encrypted_id)

def get_decrypted_object_or_404(model, encrypted_id):
    """Safe retrieval with decryption and proper error handling"""
    try:
        obj_id = decrypt_id(encrypted_id)
        return model.objects.get(pk=obj_id)
    except ValueError as e:
        logger.warning(f"Invalid ID decryption attempt: {encrypted_id}")
        raise BadRequest("Invalid item identifier")
    except model.DoesNotExist:
        logger.warning(f"Item not found for decrypted ID: {obj_id}")
        raise Http404("Item not found")
    except Exception as e:
        logger.error(f"Unexpected error during item retrieval: {str(e)}")
        raise BadRequest("Invalid request")
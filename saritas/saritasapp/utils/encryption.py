# saritasapp/utils/encryption.py
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
import base64
import logging
from django.core.exceptions import BadRequest

logger = logging.getLogger(__name__)

# Initialize encryption (add this to your settings.py if not exists)
if not hasattr(settings, 'ENCRYPTION_KEY'):
    settings.ENCRYPTION_KEY = 'your-32-url-safe-base64-key-here'  # Generate a new one for production

try:
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
except Exception as e:
    logger.error(f"Encryption setup failed: {str(e)}")
    raise

def encrypt_id(id_value):
    """Encrypt ID to URL-safe string"""
    try:
        encrypted = fernet.encrypt(str(id_value).encode())
        return base64.urlsafe_b64encode(encrypted).decode().rstrip('=')
    except Exception as e:
        logger.error(f"Encryption failed: {str(e)}")
        raise ValueError("Failed to encrypt ID")

def decrypt_id(encrypted_id):
    """Decrypt URL-safe ID back to original"""
    try:
        # Add padding if needed
        pad_length = len(encrypted_id) % 4
        if pad_length:
            encrypted_id += '=' * (4 - pad_length)
            
        decrypted = fernet.decrypt(base64.urlsafe_b64decode(encrypted_id.encode()))
        return int(decrypted.decode())
    except InvalidToken:
        logger.error("Invalid token - possible tampering")
        raise ValueError("Invalid encrypted ID")
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}")
        raise ValueError("Failed to decrypt ID")
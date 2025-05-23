from dotenv import load_dotenv
from pathlib import Path
import sys
from decouple import config
import os
from cryptography.fernet import Fernet

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR)) 

DEBUG = True
# Security settings
SECRET_KEY = os.getenv('SECRET_KEY')
FERNET_KEY = os.getenv('FERNET_KEY')
# Verify keys
if not all([SECRET_KEY, FERNET_KEY]):
    raise RuntimeError("Missing required keys in .env")

# Production settings
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']  # Add your production domain here



# Application Definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'saritasapp',
    'customerapp',
    'core',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'saritasapp.middleware.CustomerRedirectMiddleware', # Custom middleware
]

ROOT_URLCONF = 'saritas.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'saritasapp.context_processors.notifications',  # Custom context processor
                'customerapp.context_processors.notifications',
                 'customerapp.context_processors.categories_processor', # this adds categories to all pages
            ],
        },
    },
]

WSGI_APPLICATION = 'saritas.wsgi.application'

# Database Configuration
load_dotenv()  # Loads the .env file

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static and Media Files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static',]  # Add any additional static directories if necessary

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)  # Ensure media directory exists

# Authentication
AUTH_USER_MODEL = 'saritasapp.User'
LOGIN_URL = 'saritasapp:sign_in'
LOGIN_REDIRECT_URL = 'customerapp:homepage'
LOGOUT_REDIRECT_URL = 'customerapp:homepage'

# Password hashing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Email Configuration
# For development, emails will just print to the console.
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'saritascreation93@gmail.com'
EMAIL_HOST_PASSWORD = 'rlkd phun nnac ovze'  # App password (DO NOT use your real password!)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

SITE_URL = config('SITE_URL', default='http://localhost:8000')
SITE_NAME = 'Sarita\'s Event Planning'

# SMTP Email Backend Configuration for Production
if not DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='saritascreation93@gmail.com')
    EMAIL_HOST_PASSWORD = config('rlkdphunnnacovze')


# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'  # URL for Redis as the broker
CELERY_ACCEPT_CONTENT = ['json']  # Serialization format for messages
CELERY_TASK_SERIALIZER = 'json'  # How tasks are serialized
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'  # Backend to store results (can be the same Redis instance)
CELERY_TIMEZONE = 'Asia/Manila'  # Set the timezone (change if needed)

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'saritasapp': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}



# Add other necessary configurations for third-party apps or additional settings

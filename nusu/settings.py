# nusu/settings.py
import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# Allow all hosts in production (or specify your Leapcell domain)
ALLOWED_HOSTS = ['*']  # Change to your leapcell domain in production

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'cloudinary',
    'cloudinary_storage',
    'crispy_forms',
    'crispy_bootstrap5',
    # Local apps
    'users',
    'social',
    'airdrop',
    'tasks',
    'transactions',
    'tokens',
    'chat',
     'pwa',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nusu.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social.context_processors.notification_counts',
            ],
        },
    },
]

WSGI_APPLICATION = 'nusu.wsgi.application'

# Database - Uses PostgreSQL on Leapcell, SQLite locally for development
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR}/db.sqlite3'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kampala'  # Set your timezone
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
# At the bottom of settings.py
# settings.py - Remove WhiteNoise compression
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
# Media files - Cloudinary
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
    'SECURE': True,
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Custom user model
AUTH_USER_MODEL = 'users.CustomUser'

# Login/Logout URLs
LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# Redis Configuration (for mining and tasks)
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
REDIS_DB = os.environ.get('REDIS_DB', 0)

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cloudinary for social posts
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '')

# Email configuration (if needed)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Change for production

# ========== PWA SETTINGS (Copy this entire block to settings.py) ==========

# PWA app name - shows on home screen under your icon
PWA_APP_NAME = 'Nugram'

# PWA description - shows when installing
PWA_APP_DESCRIPTION = "Nugram - Connect and Share"

# Theme color - colors the top bar of the app
PWA_APP_THEME_COLOR = '#6B46C1'  # Deep purple to match your icon

# Background color - shows while the app is loading
PWA_APP_BACKGROUND_COLOR = '#ffffff'

# Display mode - 'standalone' removes browser address bar
PWA_APP_DISPLAY = 'standalone'

# Scope - which pages belong to your app
PWA_APP_SCOPE = '/'

# Screen orientation - 'any' allows both portrait and landscape
PWA_APP_ORIENTATION = 'any'

# Start URL - where the app opens first
PWA_APP_START_URL = '/'

# Status bar color - matches your theme
PWA_APP_STATUS_BAR_COLOR = 'default'

# Text direction - left to right
PWA_APP_DIR = 'ltr'

# Language - US English
PWA_APP_LANG = 'en-US'

# Your colored app icon (visible on home screen)
PWA_APP_ICONS = [
    {
        'src': '/static/images/nugram.png',
        'sizes': '1024x1024',
        'type': 'image/png',
        'purpose': 'any maskable'  # Works on all devices
    },
    {
        'src': '/static/images/nugramblack.png',
        'sizes': '1024x1024',
        'type': 'image/png',
        'purpose': 'monochrome'  # For Android 13+ themed icons
    }
]

# iOS needs separate icon configuration
PWA_APP_ICONS_APPLE = [
    {
        'src': '/static/images/nugram.png',
        'sizes': '1024x1024',
        'type': 'image/png'
    }
]

# Splash screen for mobile devices (optional but recommended)
PWA_APP_SPLASH_SCREEN = [
    {
        'src': '/static/images/nugram.png',
        'media': '(device-width: 320px) and (device-height: 568px) and (-webkit-device-pixel-ratio: 2)'
    }
]

# Disable console.log messages in browser (set to False for production)
PWA_APP_DEBUG_MODE = False
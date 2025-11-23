"""
Django Settings for SEO Content Validator

Add these to your main settings.py file.
"""

# ==============================================================================
# INSTALLED APPS
# ==============================================================================

INSTALLED_APPS = [
    # ... existing apps ...
    'rest_framework',
    'storages',  # django-storages for S3
    'corsheaders',  # CORS headers for API
    'src',  # Your SEO validator app
]

# ==============================================================================
# MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    # ... existing middleware ...
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ... rest of middleware ...
]

# ==============================================================================
# REST FRAMEWORK CONFIGURATION
# ==============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# ==============================================================================
# CORS CONFIGURATION (for API access from frontend)
# ==============================================================================

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React development server
    "http://localhost:8000",  # Django development server
    # Add your production frontend URLs here
]

CORS_ALLOW_CREDENTIALS = True

# ==============================================================================
# AWS S3 CONFIGURATION
# ==============================================================================

# AWS credentials (use environment variables in production!)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'your-bucket-name')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')

# S3 settings
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',  # Cache files for 1 day
}
AWS_DEFAULT_ACL = 'private'  # Files are private by default
AWS_S3_FILE_OVERWRITE = False  # Don't overwrite files with same name
AWS_QUERYSTRING_AUTH = True  # Generate signed URLs
AWS_QUERYSTRING_EXPIRE = 3600  # URLs expire after 1 hour

# Use S3 for file storage
DEFAULT_FILE_STORAGE = 'src.storage.GuidelineStorage'

# Optional: Use S3 for static files too
# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'seo_validator.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'src': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ==============================================================================
# ENVIRONMENT VARIABLES (.env file)
# ==============================================================================

"""
Create a .env file in your project root with:

# AWS S3
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1

# Database
DATABASE_URL=postgresql://user:password@localhost/dbname

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
"""

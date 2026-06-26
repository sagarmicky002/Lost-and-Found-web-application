"""
Configuration settings for the Lost & Found Portal
Load environment variables from .env file
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Flask Configuration
FLASK_SECRET = os.getenv("FLASK_SECRET", "super_secret_key_123")

# Database Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "flaskuser"),
    "password": os.getenv("DB_PASS", "flaskpass"),
    "database": os.getenv("DB_NAME", "lf_db")
}

# Cloudinary Configuration
CLOUDINARY_CONFIG = {
    "cloud_name": os.getenv("CLOUDINARY_NAME", ""),
    "api_key": os.getenv("CLOUDINARY_KEY", ""),
    "api_secret": os.getenv("CLOUDINARY_SECRET", "")
}

# Email Configuration
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "hkbka0302@gmail.com")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = MAIL_USERNAME

# Admin Configuration
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Session Configuration
SESSION_TIMEOUT = 120  # 120 seconds for database lock wait timeout
FUZZY_MATCH_THRESHOLD = 0.6  # Threshold for fuzzy matching similarity

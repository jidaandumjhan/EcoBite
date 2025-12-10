import os

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "supersecret")
    
    # Database Configuration
    DB_USER = os.getenv("DB_USER", "ecobite")
    DB_PASS = os.getenv("DB_PASS", "2312093")
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "ecobite")
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size

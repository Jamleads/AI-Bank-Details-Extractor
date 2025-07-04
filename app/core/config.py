"""
Application configuration settings
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings"""
    # API Settings
    API_KEY: str = "AIzaSyCrSaObz-M8amEYze6zcooE2ytYoHxr97o"  # Gemini API key
    
    # App Settings
    DEBUG: bool = True
    HOST: str = "localhost"
    PORT: int = os.environ.get("PORT", 5000)
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    PRODUCTION: bool = os.environ.get("PRODUCTION", "").lower() == "true"
    
    # File Settings
    MAX_UPLOAD_SIZE: int = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER: Path = BASE_DIR / "uploads"
    OUTPUT_FOLDER: Path = BASE_DIR / "output"
    
    # Database Settings
    DATABASE_PATH: Path = BASE_DIR / "sqlite.db"
    
    # Authentication Settings
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    # Ensure directories exist
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings() 
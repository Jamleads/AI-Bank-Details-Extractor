"""
Application configuration settings
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Setup logger
logger = logging.getLogger(__name__)

def load_aws_secrets(secret_name: str, region_name: str) -> Dict[str, Any]:
    """
    Load secrets from AWS Secrets Manager
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
        
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {str(e)}")
            return {}
        
        # Decode and return the secret
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)
        
        return {}
    except Exception as e:
        logger.error(f"Error loading AWS secrets: {str(e)}")
        return {}

class Settings:
    """Application settings"""
    def __init__(self):
        # Base directory
        self.BASE_DIR = BASE_DIR
        
        # AWS Settings - these control how we access other AWS services
        self.AWS_REGION = os.environ.get("AWS_REGION", "sa-east-1")
        self.USE_AWS_SECRETS = os.environ.get("USE_AWS_SECRETS", "").lower() == "true"
        self.AWS_SECRETS_NAME = os.environ.get("AWS_SECRETS_NAME", "")
        self.S3_BUCKET = os.environ.get("S3_BUCKET", "")
        
        # API Settings
        self.API_KEY = os.environ.get("API_KEY", "")  # Gemini API key
        
        # App Settings
        self.DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
        self.HOST = os.environ.get("HOST", "localhost")
        self.PORT = int(os.environ.get("PORT", 5000))
        self.SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
        self.PRODUCTION = os.environ.get("PRODUCTION", "").lower() == "true"
        
        # File Settings
        self.MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16MB
        self.UPLOAD_FOLDER = BASE_DIR / "uploads"
        self.OUTPUT_FOLDER = BASE_DIR / "output"
        self.USE_S3_STORAGE = os.environ.get("USE_S3_STORAGE", "").lower() == "true"
        
        # Database Settings
        self.DATABASE_TYPE = os.environ.get("DATABASE_TYPE", "sqlite").lower()  # sqlite or dynamodb
        self.DATABASE_PATH = BASE_DIR / "sqlite.db"
        
        # DynamoDB Settings
        self.AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self.DYNAMODB_ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT_URL", "")  # For local testing
        
        # Deprecated - kept for backward compatibility
        self.DYNAMODB_TABLE_PREFIX = os.environ.get("DYNAMODB_TABLE_PREFIX", "")
        
        # DynamoDB Table Names
        self.USERS_TABLE_NAME = os.environ.get("USERS_TABLE_NAME", "users")
        self.HEADER_CONFIGS_TABLE_NAME = os.environ.get("HEADER_CONFIGS_TABLE_NAME", "header-configs")
        self.RAW_EXTRACTIONS_TABLE_NAME = os.environ.get("RAW_EXTRACTIONS_TABLE_NAME", "raw-extractions")
        self.PAYMENTS_TABLE_NAME = os.environ.get("PAYMENTS_TABLE_NAME", "payments")
        self.USER_CREDENTIALS_TABLE_NAME = os.environ.get("USER_CREDENTIALS_TABLE_NAME", "user-credentials")
        
        # DynamoDB Index Names
        self.EMAIL_INDEX_NAME = os.environ.get("EMAIL_INDEX_NAME", "email-index")
        self.GOOGLE_ID_INDEX_NAME = os.environ.get("GOOGLE_ID_INDEX_NAME", "google-id-index")
        self.USER_ID_INDEX_NAME = os.environ.get("USER_ID_INDEX_NAME", "user-id-index")
        self.YATIVO_DEPOSIT_ID_INDEX_NAME = os.environ.get("YATIVO_DEPOSIT_ID_INDEX_NAME", "yativo-deposit-id-index")
        
        # Authentication Settings
        self.GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day
        
        # Yativo Payment Gateway Settings
        self.YATIVO_SECRET_KEY = os.environ.get("YATIVO_SECRET_KEY", "")
        self.YATIVO_BASE_URL = os.environ.get("YATIVO_BASE_URL", "https://sandbox.yativo.com")
        
        # Load secrets from AWS if enabled
        if self.USE_AWS_SECRETS and self.AWS_SECRETS_NAME:
            self._load_secrets_from_aws()
        
        # Set up directories
        self._setup_directories()
        
        # Validate settings
        self._validate_critical_settings()
    
    def _load_secrets_from_aws(self):
        """Load secrets from AWS Secrets Manager and apply them"""
        logger.info(f"Loading secrets from AWS Secrets Manager: {self.AWS_SECRETS_NAME}")
        secrets = load_aws_secrets(self.AWS_SECRETS_NAME, self.AWS_REGION)
        
        if secrets:
            # Update settings with secrets
            for key, value in secrets.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            logger.info("AWS secrets loaded successfully")
        else:
            logger.warning("No AWS secrets were loaded")
    
    def _setup_directories(self):
        """Create necessary directories for file storage"""
        if not self.USE_S3_STORAGE:
            os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
            os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
    
    def _validate_critical_settings(self):
        """Validate that critical settings are set, especially in production"""
        if self.PRODUCTION:
            # In production, ensure these critical settings are properly set
            critical_settings = {
                "API_KEY": self.API_KEY,
                "SECRET_KEY": self.SECRET_KEY,
                "GOOGLE_CLIENT_ID": self.GOOGLE_CLIENT_ID,
                "GOOGLE_CLIENT_SECRET": self.GOOGLE_CLIENT_SECRET,
                "YATIVO_SECRET_KEY": self.YATIVO_SECRET_KEY
            }
            
            missing = [key for key, value in critical_settings.items() if not value]
            if missing:
                logger.warning(f"Critical settings missing in production: {', '.join(missing)}")
                if self.USE_AWS_SECRETS:
                    logger.error("AWS Secrets Manager is enabled but critical settings are missing. Check your secret configuration.")


# Create settings instance
settings = Settings()
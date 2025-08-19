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


def load_gcp_secrets(secret_name: str, project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load secrets from Google Secret Manager
    
    Args:
        secret_name: Name of the secret in Google Secret Manager
        project_id: GCP Project ID (optional, uses ADC project if not provided)
        
    Returns:
        Dictionary containing the secret data
    """
    try:
        from google.cloud import secretmanager
        from google.api_core import exceptions as gcp_exceptions
        
        # Create the Secret Manager client using ADC
        client = secretmanager.SecretManagerServiceClient()
        
        # Project ID is required for Google Secret Manager
        if not project_id:
            logger.error("GCP project_id is required for Google Secret Manager")
            return {}
        
        # Build the resource name of the secret version
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        
        try:
            # Access the secret version
            response = client.access_secret_version(request={"name": name})
            
            # Decode the secret payload
            secret_string = response.payload.data.decode("UTF-8")
            return json.loads(secret_string)
            
        except gcp_exceptions.NotFound:
            logger.error(f"Secret {secret_name} not found in project {project_id}")
            return {}
        except gcp_exceptions.PermissionDenied:
            logger.error(f"Permission denied accessing secret {secret_name} in project {project_id}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Secret {secret_name} contains invalid JSON")
            return {}
            
    except ImportError:
        logger.error("google-cloud-secret-manager not installed. Install with: pip install google-cloud-secret-manager")
        return {}
    except Exception as e:
        logger.error(f"Error loading GCP secrets: {str(e)}")
        return {}

class Settings:
    """Application settings"""
    def __init__(self):
        # Base directory
        self.BASE_DIR = BASE_DIR
        
        # Cloud Provider Settings
        self.CLOUD = os.environ.get("CLOUD", "GCP").upper()  # AWS or GCP
        
        # AWS Settings - these control how we access other AWS services
        self.AWS_REGION = os.environ.get("AWS_REGION", "sa-east-1")
        self.USE_AWS_SECRETS = os.environ.get("USE_AWS_SECRETS", "").lower() == "true"
        self.AWS_SECRETS_NAME = os.environ.get("AWS_SECRETS_NAME", "")
        
        # GCP Settings - for Google Secret Manager and other GCP services
        self.GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
        self.USE_GCP_SECRETS = os.environ.get("USE_GCP_SECRETS", "").lower() == "true"
        self.GCP_SECRETS_NAME = os.environ.get("GCP_SECRETS_NAME", "")
        
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
        
        # Storage Settings
        self.USE_S3_STORAGE = os.environ.get("USE_S3_STORAGE", "").lower() == "true"
        self.USE_GCS_STORAGE = os.environ.get("USE_GCS_STORAGE", "true").lower() == "true"
        
        # Database Settings
        self.DATABASE_TYPE = os.environ.get("DATABASE_TYPE", "sqlite").lower()  # sqlite, dynamodb, or firestore
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
        self.API_KEYS_TABLE_NAME = os.environ.get("API_KEYS_TABLE_NAME", "api-keys")
        self.PRICING_ACTIONS_TABLE_NAME = os.environ.get("PRICING_ACTIONS_TABLE_NAME", "pricing-actions")

        # DynamoDB Index Names
        self.EMAIL_INDEX_NAME = os.environ.get("EMAIL_INDEX_NAME", "email-index")
        self.GOOGLE_ID_INDEX_NAME = os.environ.get("GOOGLE_ID_INDEX_NAME", "google-id-index")
        self.USER_ID_INDEX_NAME = os.environ.get("USER_ID_INDEX_NAME", "user-id-index")
        self.YATIVO_DEPOSIT_ID_INDEX_NAME = os.environ.get("YATIVO_DEPOSIT_ID_INDEX_NAME", "yativo-deposit-id-index")
        
        # Firestore Settings
        self.FIRESTORE_DATABASE_ID = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")  # Firestore database ID
        
        # Storage Bucket Settings
        self.S3_EVENTS_BUCKET = os.environ.get("S3_EVENTS_BUCKET", "")
        self.GCS_BUCKET = os.environ.get("GCS_BUCKET", "") 
        
        # Authentication Settings
        self.GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day
        
        # Yativo Payment Gateway Settings
        self.YATIVO_SECRET_KEY = os.environ.get("YATIVO_SECRET_KEY", "")
        self.YATIVO_BASE_URL = os.environ.get("YATIVO_BASE_URL", "https://sandbox.yativo.com")

        # Load secrets based on cloud provider
        self._load_secrets_from_cloud()
        
        # Set up directories
        self._setup_directories()
        
        # Validate settings
        self._validate_critical_settings()
    
    def _load_secrets_from_cloud(self):
        """Load secrets from the appropriate cloud provider"""
        if self.CLOUD == "AWS" and self.USE_AWS_SECRETS and self.AWS_SECRETS_NAME:
            self._load_secrets_from_aws()
        elif self.CLOUD == "GCP" and self.USE_GCP_SECRETS and self.GCP_SECRETS_NAME:
            self._load_secrets_from_gcp()
        elif self.USE_AWS_SECRETS and self.AWS_SECRETS_NAME:
            # Fallback to AWS for backward compatibility
            logger.info("No CLOUD setting found, defaulting to AWS Secrets Manager")
            self._load_secrets_from_aws()
        elif self.USE_GCP_SECRETS and self.GCP_SECRETS_NAME:
            # Fallback to GCP if AWS not configured
            logger.info("No CLOUD setting found, defaulting to GCP Secrets Manager")
            self._load_secrets_from_gcp()
        else:
            logger.info("No cloud secrets manager configured")
    
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
    
    def _load_secrets_from_gcp(self):
        """Load secrets from Google Secret Manager and apply them"""
        secrets = load_gcp_secrets(self.GCP_SECRETS_NAME, self.GCP_PROJECT_ID)
        
        if secrets:
            # Update settings with secrets
            for key, value in secrets.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            logger.info("GCP secrets loaded successfully")
        else:
            logger.warning("No GCP secrets were loaded")
    
    def _setup_directories(self):
        """Create necessary directories for file storage"""
        # Only create directories if not using cloud storage and not in Lambda environment
        if not (self.USE_S3_STORAGE or self.USE_GCS_STORAGE) and not os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
            try:
                os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
                os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
            except OSError as e:
                # In Lambda or other read-only environments, this will fail silently
                logger.warning(f"Could not create directories (likely read-only filesystem): {e}")
                pass
    
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
            
            # Add database-specific validation
            if self.DATABASE_TYPE == "firestore":
                # Firestore uses ADC - no additional settings required
                # ADC will automatically detect project and credentials
                pass
            elif self.DATABASE_TYPE == "dynamodb":
                dynamodb_settings = {
                    "AWS_ACCESS_KEY_ID": self.AWS_ACCESS_KEY_ID,
                    "AWS_SECRET_ACCESS_KEY": self.AWS_SECRET_ACCESS_KEY
                }
                critical_settings.update(dynamodb_settings)
            
            # Add cloud-specific secrets validation
            if self.CLOUD == "AWS" and self.USE_AWS_SECRETS:
                aws_secrets_settings = {
                    "AWS_SECRETS_NAME": self.AWS_SECRETS_NAME,
                    "AWS_REGION": self.AWS_REGION
                }
                critical_settings.update(aws_secrets_settings)
            elif self.CLOUD == "GCP" and self.USE_GCP_SECRETS:
                gcp_secrets_settings = {
                    "GCP_SECRETS_NAME": self.GCP_SECRETS_NAME,
                    "GCP_PROJECT_ID": self.GCP_PROJECT_ID
                }
                critical_settings.update(gcp_secrets_settings)
            
            missing = [key for key, value in critical_settings.items() if not value]
            if missing:
                logger.warning(f"Critical settings missing in production: {', '.join(missing)}")
                
                # Cloud-specific error messages
                if self.CLOUD == "AWS" and self.USE_AWS_SECRETS:
                    logger.error("AWS Secrets Manager is enabled but critical settings are missing. Check your AWS secret configuration.")
                elif self.CLOUD == "GCP" and self.USE_GCP_SECRETS:
                    logger.error("Google Secret Manager is enabled but critical settings are missing. Check your GCP secret configuration.")
                elif self.USE_AWS_SECRETS:
                    logger.error("AWS Secrets Manager is enabled but critical settings are missing. Check your secret configuration.")
                elif self.USE_GCP_SECRETS:
                    logger.error("Google Secret Manager is enabled but critical settings are missing. Check your secret configuration.")
                elif self.DATABASE_TYPE == "firestore":
                    logger.info("Firestore will use Application Default Credentials (ADC) for authentication.")


# Create settings instance
settings = Settings()
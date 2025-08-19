"""
Environment detection utilities
"""
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def detect_cloud_environment() -> bool:
    """
    Detect if running in cloud environment
    
    Returns:
        True if running in cloud, False if running locally
    """
    # Check for AWS Lambda
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        logger.info("Detected AWS Lambda environment")
        return True
    
    # Check for GCP Cloud Functions
    if os.environ.get('FUNCTION_NAME') or os.environ.get('GCP_PROJECT'):
        logger.info("Detected GCP Cloud Functions environment")
        return True
    
    # Check for explicit cloud flag
    if os.environ.get('CLOUD_ENVIRONMENT', '').lower() == 'true':
        logger.info("Detected explicit cloud environment flag")
        return True
    
    # Check for production flag with S3 usage
    if settings.PRODUCTION and settings.USE_S3_STORAGE:
        logger.info("Detected production environment with S3 storage")
        return True
    
    # Check for AWS ECS/Fargate
    if os.environ.get('AWS_EXECUTION_ENV'):
        logger.info("Detected AWS container environment")
        return True
        
    logger.info("Detected local development environment")
    return False


def get_processing_mode() -> str:
    """
    Get the processing mode based on environment
    
    Returns:
        'cloud' for cloud-based concurrent API processing
        'local' for local multiprocessing
    """
    return 'cloud' if detect_cloud_environment() else 'local'


def get_max_concurrent_files() -> int:
    """
    Get maximum concurrent files based on environment
    
    Returns:
        Number of files that can be processed concurrently
    """
    if detect_cloud_environment():
        # In cloud, we can handle more concurrent API calls
        return int(os.environ.get('MAX_CONCURRENT_FILES', '10'))
    else:
        # Local processing limited by CPU cores
        import multiprocessing
        return min(int(os.environ.get('MAX_CONCURRENT_FILES', '6')), multiprocessing.cpu_count())

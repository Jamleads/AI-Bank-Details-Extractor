import os
import sys
import logging
from pathlib import Path

# Add the current directory to Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mangum import Mangum
from main import app

# Configure logging for Lambda/CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove existing handlers to avoid duplicate logs
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Add CloudWatch handler
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(handler)

# Create Mangum handler for Lambda
handler = Mangum(app, lifespan="off")

def lambda_handler(event, context):
    """AWS Lambda handler function"""
    try:
        return handler(event, context)
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        raise 
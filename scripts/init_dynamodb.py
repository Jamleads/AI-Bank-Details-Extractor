#!/usr/bin/env python3
"""
Script to initialize DynamoDB tables
"""
import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.adapter import db_adapter
from app.db.dynamodb import dynamodb_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_dynamodb():
    """Initialize DynamoDB tables"""
    logger.info("Initializing DynamoDB tables")
    
    # Check if using DynamoDB
    if settings.DATABASE_TYPE != "dynamodb":
        logger.warning("DATABASE_TYPE is not set to 'dynamodb'. Current value: %s", settings.DATABASE_TYPE)
        choice = input("Do you want to continue initializing DynamoDB tables? (y/n): ")
        if choice.lower() != 'y':
            logger.info("Aborting initialization")
            return
    
    # Create tables
    try:
        dynamodb_service.create_tables()
        logger.info("DynamoDB tables initialized successfully")
    except Exception as e:
        logger.error("Error initializing DynamoDB tables: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    init_dynamodb()
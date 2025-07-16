#!/usr/bin/env python
"""
Script to migrate Google Drive credentials from files to DynamoDB
"""
import os
import sys
import json
import logging
import glob

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.adapter import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_credentials():
    """Migrate Google Drive credentials from files to database"""
    logger.info("Starting migration of Google Drive credentials to database")
    
    # Ensure DynamoDB is configured
    os.environ["DATABASE_TYPE"] = "dynamodb"
    
    # Get all credential files
    credentials_dir = os.path.join(settings.BASE_DIR, 'user_credentials')
    if not os.path.exists(credentials_dir):
        logger.info("No credentials directory found, nothing to migrate")
        return
    
    credential_files = glob.glob(os.path.join(credentials_dir, 'drive_credentials_*.json'))
    logger.info(f"Found {len(credential_files)} credential files to migrate")
    
    migrated_count = 0
    for cred_file in credential_files:
        try:
            # Extract user ID from filename
            filename = os.path.basename(cred_file)
            user_id = filename.replace('drive_credentials_', '').replace('.json', '')
            
            logger.info(f"Migrating credentials for user {user_id}")
            
            # Read credentials from file
            with open(cred_file, 'r') as f:
                creds_dict = json.load(f)
            
            # Store credentials in database
            db.store_user_credentials(user_id, 'google_drive', creds_dict)
            
            # Backup the original file
            backup_file = f"{cred_file}.bak"
            os.rename(cred_file, backup_file)
            logger.info(f"Created backup of credential file: {backup_file}")
            
            migrated_count += 1
        except Exception as e:
            logger.error(f"Error migrating credentials from {cred_file}: {str(e)}")
    
    logger.info(f"Successfully migrated {migrated_count} credential files to database")


if __name__ == "__main__":
    migrate_credentials() 
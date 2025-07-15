#!/usr/bin/env python3
"""
Script to check if local DynamoDB is running
"""
import os
import sys
import boto3
import logging
from botocore.exceptions import ClientError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dynamodb_connection(endpoint_url="http://localhost:8000"):
    """Check if DynamoDB local is accessible"""
    try:
        # Create a DynamoDB client
        dynamodb = boto3.client(
            'dynamodb',
            endpoint_url=endpoint_url,
            region_name='us-east-1',
            aws_access_key_id='dummy',
            aws_secret_access_key='dummy'
        )
        
        # List tables to check connection
        response = dynamodb.list_tables()
        tables = response.get('TableNames', [])
        
        logger.info(f"Successfully connected to DynamoDB at {endpoint_url}")
        logger.info(f"Found {len(tables)} tables: {', '.join(tables) if tables else 'No tables yet'}")
        return True
    
    except ClientError as e:
        logger.error(f"Failed to connect to DynamoDB: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = check_dynamodb_connection()
    sys.exit(0 if success else 1) 
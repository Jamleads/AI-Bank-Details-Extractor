#!/usr/bin/env python3
"""
Check AWS connectivity and credentials
"""
import os
import sys
import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.config import settings, load_aws_secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_aws_credentials():
    """Check if AWS credentials are available and valid"""
    try:
        logger.info("Checking AWS credentials...")
        session = boto3.Session(region_name=settings.AWS_REGION)
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        logger.info(f"AWS credentials are valid. Account ID: {identity['Account']}")
        logger.info(f"Current user/role: {identity['Arn']}")
        return True
    except NoCredentialsError:
        logger.error("No AWS credentials found. Please run 'aws configure' or set environment variables.")
        return False
    except Exception as e:
        logger.error(f"Error checking AWS credentials: {str(e)}")
        return False

def check_secrets_manager():
    """Check access to AWS Secrets Manager"""
    if not settings.AWS_SECRETS_NAME:
        logger.warning("No secrets name configured. Skipping Secrets Manager check.")
        return False
    
    try:
        logger.info(f"Checking access to Secrets Manager secret: {settings.AWS_SECRETS_NAME}")
        session = boto3.Session(region_name=settings.AWS_REGION)
        client = session.client('secretsmanager')
        
        # Test listing secrets
        secrets = client.list_secrets(MaxResults=10)
        logger.info(f"Successfully listed secrets. Found {len(secrets.get('SecretList', []))} secrets.")
        
        # Try to access the specific secret if configured
        if settings.AWS_SECRETS_NAME:
            try:
                response = client.describe_secret(SecretId=settings.AWS_SECRETS_NAME)
                logger.info(f"Successfully accessed secret: {settings.AWS_SECRETS_NAME}")
                
                # Test loading the secret
                secrets = load_aws_secrets(settings.AWS_SECRETS_NAME, settings.AWS_REGION)
                if secrets:
                    logger.info("Secret contents loaded successfully")
                    # Don't log actual secret values for security
                    logger.info(f"Secret contains {len(secrets)} keys")
                else:
                    logger.warning(f"Secret {settings.AWS_SECRETS_NAME} exists but couldn't load contents")
                
                return True
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    logger.error(f"Secret {settings.AWS_SECRETS_NAME} does not exist")
                else:
                    logger.error(f"Error accessing secret: {str(e)}")
                return False
    except Exception as e:
        logger.error(f"Error checking Secrets Manager: {str(e)}")
        return False

def check_s3_bucket():
    """Check access to S3 bucket"""
    if not settings.S3_EVENTS_BUCKET:
        logger.warning("No S3 bucket configured. Skipping S3 check.")
        return False
    
    try:
        logger.info(f"Checking access to S3 bucket: {settings.S3_EVENTS_BUCKET}")
        session = boto3.Session(region_name=settings.AWS_REGION)
        s3 = session.client('s3')
        
        # Test if bucket exists
        try:
            s3.head_bucket(Bucket=settings.S3_EVENTS_BUCKET)
            logger.info(f"S3 bucket {settings.S3_EVENTS_BUCKET} exists and is accessible")
            
            # Test listing objects
            response = s3.list_objects_v2(Bucket=settings.S3_EVENTS_BUCKET, MaxKeys=5)
            if 'Contents' in response:
                logger.info(f"Successfully listed objects in bucket. Found {len(response['Contents'])} objects.")
            else:
                logger.info("Bucket exists but is empty")
            
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"S3 bucket {settings.S3_EVENTS_BUCKET} does not exist")
            elif e.response['Error']['Code'] == '403':
                logger.error(f"Access denied to S3 bucket {settings.S3_EVENTS_BUCKET}")
            else:
                logger.error(f"Error accessing S3 bucket: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error checking S3 bucket: {str(e)}")
        return False

def check_dynamodb():
    """Check access to DynamoDB tables"""
    try:
        logger.info("Checking access to DynamoDB...")
        session = boto3.Session(region_name=settings.AWS_REGION)
        dynamodb = session.client('dynamodb')
        
        # Test listing tables
        response = dynamodb.list_tables(Limit=100)
        tables = response.get('TableNames', [])
        
        logger.info(f"Successfully listed DynamoDB tables. Found {len(tables)} tables.")
        
        # Check for specific tables
        required_tables = [
            settings.USERS_TABLE_NAME,
            settings.HEADER_CONFIGS_TABLE_NAME,
            settings.RAW_EXTRACTIONS_TABLE_NAME,
            settings.PAYMENTS_TABLE_NAME,
            settings.USER_CREDENTIALS_TABLE_NAME
        ]
        
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            logger.warning(f"Missing required tables: {', '.join(missing_tables)}")
        else:
            logger.info("All required tables exist")
            
            # Check for indexes on tables
            for table_name in required_tables:
                if table_name in tables:
                    try:
                        table_description = dynamodb.describe_table(TableName=table_name)
                        gsi_list = table_description.get('Table', {}).get('GlobalSecondaryIndexes', [])
                        
                        if gsi_list:
                            index_names = [index['IndexName'] for index in gsi_list]
                            logger.info(f"Table {table_name} has indexes: {', '.join(index_names)}")
                            
                            # Check for required indexes based on table
                            if table_name == settings.USERS_TABLE_NAME:
                                required_indexes = [settings.EMAIL_INDEX_NAME, settings.GOOGLE_ID_INDEX_NAME]
                                for idx in required_indexes:
                                    if idx not in index_names:
                                        logger.warning(f"Users table missing required index: {idx}")
                                        
                            elif table_name == settings.HEADER_CONFIGS_TABLE_NAME:
                                if settings.USER_ID_INDEX_NAME not in index_names:
                                    logger.warning(f"Header configs table missing required index: {settings.USER_ID_INDEX_NAME}")
                                    
                            elif table_name == settings.RAW_EXTRACTIONS_TABLE_NAME:
                                if settings.USER_ID_INDEX_NAME not in index_names:
                                    logger.warning(f"Raw extractions table missing required index: {settings.USER_ID_INDEX_NAME}")
                                    
                            elif table_name == settings.PAYMENTS_TABLE_NAME:
                                required_indexes = [settings.USER_ID_INDEX_NAME, settings.YATIVO_DEPOSIT_ID_INDEX_NAME]
                                for idx in required_indexes:
                                    if idx not in index_names:
                                        logger.warning(f"Payments table missing required index: {idx}")
                        else:
                            if table_name != settings.USER_CREDENTIALS_TABLE_NAME:  # User credentials table doesn't have GSIs
                                logger.warning(f"Table {table_name} has no indexes")
                            else:
                                logger.info(f"Table {table_name} has no GSIs (as expected)")
                    except Exception as e:
                        logger.error(f"Error checking indexes for table {table_name}: {str(e)}")
        
        return len(missing_tables) == 0
    except Exception as e:
        logger.error(f"Error checking DynamoDB: {str(e)}")
        return False

def main():
    """Run all checks"""
    logger.info("=== AWS Services Connectivity Check ===")
    logger.info(f"AWS Region: {settings.AWS_REGION}")
    
    success = True
    
    # Check AWS credentials
    if not check_aws_credentials():
        success = False
    
    # Check Secrets Manager
    if not check_secrets_manager():
        success = False
    
    # Check S3
    if not check_s3_bucket():
        success = False
    
    # Check DynamoDB
    if not check_dynamodb():
        success = False
    
    # Print summary
    if success:
        logger.info("✅ All AWS checks passed!")
    else:
        logger.warning("⚠️ Some AWS checks failed. Review the logs for details.")
        
    # Warn about deprecated settings
    if settings.DYNAMODB_TABLE_PREFIX:
        logger.warning("⚠️ DYNAMODB_TABLE_PREFIX is deprecated and will be removed in a future version. Use specific table names instead.")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python
"""
Test script for user credentials storage in DynamoDB
"""
import os
import sys
import json
import uuid
import logging
from decimal import Decimal
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set environment variables for testing
os.environ["DATABASE_TYPE"] = "dynamodb"
os.environ["DYNAMODB_TABLE_PREFIX"] = "test_"
os.environ["DYNAMODB_ENDPOINT_URL"] = "http://localhost:8000"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

try:
    from app.core.config import settings
    from app.db.adapter import db
    from app.db.dynamodb import dynamodb_service
    from app.services.google_drive_service import GoogleDriveService
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)

# Test results
test_results = {
    "passed": 0,
    "failed": 0,
    "total": 0
}

# Test data
TEST_USER_ID = f"test-{uuid.uuid4()}"
TEST_CREDENTIALS = {
    'token': f"ya29.test-token-{uuid.uuid4()}",
    'refresh_token': f"1//test-refresh-token-{uuid.uuid4()}",
    'token_uri': "https://oauth2.googleapis.com/token",
    'client_id': "test-client-id.apps.googleusercontent.com",
    'client_secret': "test-client-secret",
    'scopes': [
        "https://www.googleapis.com/auth/drive.file",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ]
}


def run_test(test_name: str, test_func, *args, **kwargs):
    """Run a test and record the result"""
    test_results["total"] += 1
    print(f"\nRunning test: {test_name}")
    try:
        result = test_func(*args, **kwargs)
        test_results["passed"] += 1
        print(f"✅ Test passed: {test_name}")
        return result
    except Exception as e:
        test_results["failed"] += 1
        print(f"❌ Test failed: {test_name}")
        print(f"Error: {str(e)}")
        return None


def test_create_tables():
    """Test creating DynamoDB tables including the user credentials table"""
    dynamodb_service.create_tables()
    return True


def test_store_credentials():
    """Test storing user credentials in DynamoDB"""
    result = db.store_user_credentials(TEST_USER_ID, 'google_drive', TEST_CREDENTIALS)
    assert result is not None
    assert result['user_id'] == str(TEST_USER_ID)
    assert result['credential_type'] == 'google_drive'
    assert 'credentials' in result
    assert result['credentials']['token'] == TEST_CREDENTIALS['token']
    return result


def test_get_credentials():
    """Test retrieving user credentials from DynamoDB"""
    result = db.get_user_credentials(TEST_USER_ID, 'google_drive')
    assert result is not None
    assert result['user_id'] == str(TEST_USER_ID)
    assert result['credential_type'] == 'google_drive'
    assert 'credentials' in result
    assert result['credentials']['token'] == TEST_CREDENTIALS['token']
    return result


def test_google_drive_service_store():
    """Test storing credentials using GoogleDriveService"""
    # Create Google credentials object
    credentials = Credentials(
        token=TEST_CREDENTIALS['token'],
        refresh_token=TEST_CREDENTIALS['refresh_token'],
        token_uri=TEST_CREDENTIALS['token_uri'],
        client_id=TEST_CREDENTIALS['client_id'],
        client_secret=TEST_CREDENTIALS['client_secret'],
        scopes=TEST_CREDENTIALS['scopes']
    )
    
    # Store credentials
    GoogleDriveService.store_credentials(TEST_USER_ID, credentials)
    
    # Verify storage
    result = db.get_user_credentials(TEST_USER_ID, 'google_drive')
    assert result is not None
    assert result['credentials']['token'] == TEST_CREDENTIALS['token']
    return result


def test_google_drive_service_get():
    """Test retrieving credentials using GoogleDriveService"""
    credentials = GoogleDriveService.get_stored_credentials(TEST_USER_ID)
    assert credentials is not None
    assert credentials.token == TEST_CREDENTIALS['token']
    assert credentials.refresh_token == TEST_CREDENTIALS['refresh_token']
    assert credentials.client_id == TEST_CREDENTIALS['client_id']
    return credentials


def test_delete_credentials():
    """Test deleting user credentials from DynamoDB"""
    result = db.delete_user_credentials(TEST_USER_ID, 'google_drive')
    assert result is not None
    
    # Verify deletion
    check = db.get_user_credentials(TEST_USER_ID, 'google_drive')
    assert check is None
    return result


def main():
    """Run all tests"""
    print("Starting user credentials storage tests...")
    
    # Create tables
    run_test("Create Tables", test_create_tables)
    
    # Test direct DB operations
    run_test("Store Credentials", test_store_credentials)
    run_test("Get Credentials", test_get_credentials)
    
    # Test GoogleDriveService integration
    run_test("GoogleDriveService Store", test_google_drive_service_store)
    run_test("GoogleDriveService Get", test_google_drive_service_get)
    
    # Test deletion
    run_test("Delete Credentials", test_delete_credentials)
    
    # Print summary
    print("\n--- Test Summary ---")
    print(f"Total tests: {test_results['total']}")
    print(f"Passed: {test_results['passed']}")
    print(f"Failed: {test_results['failed']}")
    
    if test_results['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main() 
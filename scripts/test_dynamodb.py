#!/usr/bin/env python
"""
Test script for DynamoDB functions
"""
import os
import sys
import uuid
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

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
    from app.db.dynamodb import dynamodb_service
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)

# Test data
TEST_USER = {
    "email": f"test-{uuid.uuid4()}@example.com",
    "google_id": f"google-{uuid.uuid4()}",
    "name": "Test User",
    "picture": "https://example.com/picture.jpg",
    "subscription_tier": "basic"
}

TEST_BANK_RECORD = {
    "source_pdf": "test-bank-statement.pdf",
    "account_number": "12345678",
    "account_name": "Test Account",
    "bank_name": "Test Bank",
    "sort_code": "12-34-56",
    "iban": "GB12ABCD12345612345678",
    "swift_code": "TESTGB2L",
    "routing_number": "123456789",
    "bsb_code": "123-456",
    "branch_code": "001",
    "branch_address": "123 Test Street, Test City",
    "account_type": "Current",
    "currency": "GBP",
    "balance": "1000.00",
    "other_details": "Additional test details"
}

TEST_HEADER_CONFIG = {
    "name": "Test Config",
    "is_default": 1,
    "header_mappings": {
        "account_number": "Account Number",
        "bank_name": "Bank Name",
        "sort_code": "Sort Code"
    },
    "file_format": "csv"
}

TEST_RAW_EXTRACTION = {
    "source_pdf": "test-extraction.pdf",
    "raw_data": {
        "extracted_text": "This is test extracted text",
        "confidence": Decimal("0.95")
    }
}

TEST_PAYMENT = {
    "amount": Decimal("19.99"),
    "currency": "USD",
    "tier": "basic",
    "yativo_deposit_id": f"yativo-{uuid.uuid4()}",
    "yativo_customer_id": f"customer-{uuid.uuid4()}",
    "payment_method": "card",
    "checkout_url": "https://example.com/checkout"
}

# Test results
test_results = {
    "passed": 0,
    "failed": 0,
    "total": 0
}

# Test user data
created_user = None
created_bank_record = None
created_header_config = None
created_raw_extraction = None
created_payment = None


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

def test_create_user():
    """Test creating a user"""
    user = dynamodb_service.create_user(TEST_USER)
    assert user is not None
    assert "id" in user
    assert user["email"] == TEST_USER["email"]
    assert user["google_id"] == TEST_USER["google_id"]
    return user


def test_get_user_by_id(user_id: str):
    """Test getting a user by ID"""
    user = dynamodb_service.get_user_by_id(user_id)
    assert user is not None
    assert user["id"] == user_id
    return user


def test_get_user_by_email(email: str):
    """Test getting a user by email"""
    user = dynamodb_service.get_user_by_email(email)
    assert user is not None
    assert user["email"] == email
    return user


def test_get_user_by_google_id(google_id: str):
    """Test getting a user by Google ID"""
    user = dynamodb_service.get_user_by_google_id(google_id)
    assert user is not None
    assert user["google_id"] == google_id
    return user


def test_update_user(user_id: str):
    """Test updating a user"""
    update_data = {
        "name": "Updated Test User",
        "subscription_tier": "pro"
    }
    user = dynamodb_service.update_user(user_id, update_data)
    assert user is not None
    assert user["name"] == update_data["name"]
    assert user["subscription_tier"] == update_data["subscription_tier"]
    return user


def test_create_bank_record(user_id: str):
    """Test creating a bank record"""
    record_data = TEST_BANK_RECORD.copy()
    record_data["user_id"] = user_id
    record = dynamodb_service.create_bank_record(record_data)
    assert record is not None
    assert "id" in record
    assert record["user_id"] == user_id
    assert record["account_number"] == TEST_BANK_RECORD["account_number"]
    return record


def test_get_bank_records_by_user(user_id: str):
    """Test getting bank records by user"""
    records = dynamodb_service.get_bank_records_by_user(user_id)
    assert isinstance(records, list)
    assert len(records) > 0
    assert records[0]["user_id"] == user_id
    return records


def test_create_header_config(user_id: str):
    """Test creating a header config"""
    config_data = TEST_HEADER_CONFIG.copy()
    config_data["user_id"] = user_id
    config = dynamodb_service.create_header_config(config_data)
    assert config is not None
    assert "id" in config
    assert config["user_id"] == user_id
    assert config["name"] == TEST_HEADER_CONFIG["name"]
    return config


def test_get_header_configs_by_user(user_id: str):
    """Test getting header configs by user"""
    configs = dynamodb_service.get_header_configs_by_user(user_id)
    assert isinstance(configs, list)
    assert len(configs) > 0
    assert configs[0]["user_id"] == user_id
    return configs


def test_get_header_config(config_id: str):
    """Test getting a header config by ID"""
    config = dynamodb_service.get_header_config(config_id)
    assert config is not None
    assert config["id"] == config_id
    return config


def test_update_header_config(config_id: str):
    """Test updating a header config"""
    update_data = {
        "name": "Updated Config",
        "is_default": 0,
        "header_mappings": {
            "account_number": "Account #",
            "bank_name": "Bank",
        }
    }
    config = dynamodb_service.update_header_config(config_id, update_data)
    assert config is not None
    assert config["name"] == update_data["name"]
    assert config["is_default"] == update_data["is_default"]
    return config


def test_create_raw_extraction(user_id: str):
    """Test creating a raw extraction"""
    extraction_data = TEST_RAW_EXTRACTION.copy()
    extraction_data["user_id"] = user_id
    extraction = dynamodb_service.create_raw_extraction(extraction_data)
    assert extraction is not None
    assert "id" in extraction
    assert extraction["user_id"] == user_id
    return extraction


def test_get_raw_extractions_by_user(user_id: str):
    """Test getting raw extractions by user"""
    extractions = dynamodb_service.get_raw_extractions_by_user(user_id)
    assert isinstance(extractions, list)
    assert len(extractions) > 0
    assert extractions[0]["user_id"] == user_id
    return extractions


def test_create_payment(user_id: str):
    """Test creating a payment"""
    payment_data = TEST_PAYMENT.copy()
    payment_data["user_id"] = user_id
    payment = dynamodb_service.create_payment(payment_data)
    assert payment is not None
    assert "id" in payment
    assert payment["user_id"] == user_id
    assert Decimal(str(payment["amount"])) == TEST_PAYMENT["amount"]
    return payment


def test_get_payment(payment_id: str):
    """Test getting a payment by ID"""
    payment = dynamodb_service.get_payment(payment_id)
    assert payment is not None
    assert payment["id"] == payment_id
    return payment


def test_get_payments_by_user(user_id: str):
    """Test getting payments by user"""
    payments = dynamodb_service.get_payments_by_user(user_id)
    assert isinstance(payments, list)
    assert len(payments) > 0
    assert payments[0]["user_id"] == user_id
    return payments


def test_get_payment_by_yativo_deposit_id(yativo_deposit_id: str):
    """Test getting a payment by Yativo deposit ID"""
    payment = dynamodb_service.get_payment_by_yativo_deposit_id(yativo_deposit_id)
    assert payment is not None
    assert payment["yativo_deposit_id"] == yativo_deposit_id
    return payment


def test_update_payment(payment_id: str):
    """Test updating a payment"""
    update_data = {
        "status": "completed",
        "payment_method": "paypal"
    }
    payment = dynamodb_service.update_payment(payment_id, update_data)
    assert payment is not None
    assert payment["status"] == update_data["status"]
    assert payment["payment_method"] == update_data["payment_method"]
    return payment


def test_delete_raw_extractions_by_user(user_id: str):
    """Test deleting raw extractions by user"""
    count = dynamodb_service.delete_raw_extractions_by_user(user_id)
    assert count >= 0
    extractions = dynamodb_service.get_raw_extractions_by_user(user_id)
    assert len(extractions) == 0
    return count


def test_delete_bank_records_by_user(user_id: str):
    """Test deleting bank records by user"""
    count = dynamodb_service.delete_bank_records_by_user(user_id)
    assert count >= 0
    records = dynamodb_service.get_bank_records_by_user(user_id)
    assert len(records) == 0
    return count


def decimal_default(obj):
    """Helper function to convert Decimal to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def main():
    """Run all tests"""
    print("Starting DynamoDB tests...")

    # User tests
    global created_user
    created_user = run_test("Create User", test_create_user)
    if not created_user:
        print("Failed to create test user. Aborting remaining tests.")
        return
    
    user_id = created_user["id"]
    run_test("Get User by ID", test_get_user_by_id, user_id)
    run_test("Get User by Email", test_get_user_by_email, created_user["email"])
    run_test("Get User by Google ID", test_get_user_by_google_id, created_user["google_id"])
    run_test("Update User", test_update_user, user_id)
    
    # Bank record tests
    global created_bank_record
    created_bank_record = run_test("Create Bank Record", test_create_bank_record, user_id)
    run_test("Get Bank Records by User", test_get_bank_records_by_user, user_id)
    
    # Header config tests
    global created_header_config
    created_header_config = run_test("Create Header Config", test_create_header_config, user_id)
    if created_header_config:
        config_id = created_header_config["id"]
        run_test("Get Header Configs by User", test_get_header_configs_by_user, user_id)
        run_test("Get Header Config by ID", test_get_header_config, config_id)
        run_test("Update Header Config", test_update_header_config, config_id)
    
    # Raw extraction tests
    global created_raw_extraction
    created_raw_extraction = run_test("Create Raw Extraction", test_create_raw_extraction, user_id)
    run_test("Get Raw Extractions by User", test_get_raw_extractions_by_user, user_id)
    
    # Payment tests
    global created_payment
    created_payment = run_test("Create Payment", test_create_payment, user_id)
    if created_payment:
        payment_id = created_payment["id"]
        run_test("Get Payment by ID", test_get_payment, payment_id)
        run_test("Get Payments by User", test_get_payments_by_user, user_id)
        run_test("Get Payment by Yativo Deposit ID", test_get_payment_by_yativo_deposit_id, created_payment["yativo_deposit_id"])
        run_test("Update Payment", test_update_payment, payment_id)
    
    # Deletion tests
    run_test("Delete Raw Extractions by User", test_delete_raw_extractions_by_user, user_id)
    run_test("Delete Bank Records by User", test_delete_bank_records_by_user, user_id)
    
    # Print summary
    print("\n--- Test Summary ---")
    print(f"Total tests: {test_results['total']}")
    print(f"Passed: {test_results['passed']}")
    print(f"Failed: {test_results['failed']}")
    
    if test_results['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main() 
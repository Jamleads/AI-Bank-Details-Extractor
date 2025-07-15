"""
DynamoDB database operations
"""
import os
import boto3
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from boto3.dynamodb.conditions import Key, Attr

from app.core.config import settings

# Table names
USERS_TABLE = f"{settings.DYNAMODB_TABLE_PREFIX}users"
BANK_RECORDS_TABLE = f"{settings.DYNAMODB_TABLE_PREFIX}bank_records"
HEADER_CONFIGS_TABLE = f"{settings.DYNAMODB_TABLE_PREFIX}header_configs"
RAW_EXTRACTIONS_TABLE = f"{settings.DYNAMODB_TABLE_PREFIX}raw_extractions"
PAYMENTS_TABLE = f"{settings.DYNAMODB_TABLE_PREFIX}payments"


class DynamoDBService:
    """DynamoDB service for database operations"""

    def __init__(self):
        """Initialize DynamoDB service"""
        # Initialize DynamoDB client
        kwargs = {}
        if settings.DYNAMODB_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL

        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            **kwargs
        )

    def create_tables(self):
        """Create DynamoDB tables if they don't exist"""
        # Users table
        self._create_users_table()
        # Bank records table
        self._create_bank_records_table()
        # Header configs table
        self._create_header_configs_table()
        # Raw extractions table
        self._create_raw_extractions_table()
        # Payments table
        self._create_payments_table()

    def _create_users_table(self):
        """Create users table"""
        try:
            self.dynamodb.create_table(
                TableName=USERS_TABLE,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'},  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'},
                    {'AttributeName': 'google_id', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'email-index',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'google-id-index',
                        'KeySchema': [
                            {'AttributeName': 'google_id', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            print(f"Created {USERS_TABLE} table")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"{USERS_TABLE} table already exists")

    def _create_bank_records_table(self):
        """Create bank records table"""
        try:
            self.dynamodb.create_table(
                TableName=BANK_RECORDS_TABLE,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'},  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'user-id-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            print(f"Created {BANK_RECORDS_TABLE} table")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"{BANK_RECORDS_TABLE} table already exists")

    def _create_header_configs_table(self):
        """Create header configs table"""
        try:
            self.dynamodb.create_table(
                TableName=HEADER_CONFIGS_TABLE,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'},  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'user-id-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            print(f"Created {HEADER_CONFIGS_TABLE} table")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"{HEADER_CONFIGS_TABLE} table already exists")

    def _create_raw_extractions_table(self):
        """Create raw extractions table"""
        try:
            self.dynamodb.create_table(
                TableName=RAW_EXTRACTIONS_TABLE,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'},  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'user-id-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            print(f"Created {RAW_EXTRACTIONS_TABLE} table")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"{RAW_EXTRACTIONS_TABLE} table already exists")

    def _create_payments_table(self):
        """Create payments table"""
        try:
            self.dynamodb.create_table(
                TableName=PAYMENTS_TABLE,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'},  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'yativo_deposit_id', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'user-id-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'yativo-deposit-id-index',
                        'KeySchema': [
                            {'AttributeName': 'yativo_deposit_id', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            print(f"Created {PAYMENTS_TABLE} table")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"{PAYMENTS_TABLE} table already exists")

    # User operations
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        table = self.dynamodb.Table(USERS_TABLE)
        response = table.query(
            IndexName='email-index',
            KeyConditionExpression=Key('email').eq(email)
        )
        items = response.get('Items', [])
        return items[0] if items else None

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Google ID"""
        table = self.dynamodb.Table(USERS_TABLE)
        response = table.query(
            IndexName='google-id-index',
            KeyConditionExpression=Key('google_id').eq(google_id)
        )
        items = response.get('Items', [])
        return items[0] if items else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        table = self.dynamodb.Table(USERS_TABLE)
        response = table.get_item(Key={'id': user_id})
        return response.get('Item')

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        table = self.dynamodb.Table(USERS_TABLE)
        user_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        user_item = {
            'id': user_id,
            'email': user_data['email'],
            'google_id': user_data['google_id'],
            'name': user_data.get('name'),
            'picture': user_data.get('picture'),
            'created_at': timestamp,
            'last_login': timestamp,
            'subscription_tier': user_data.get('subscription_tier', 'free'),
            'subscription_updated_at': timestamp
        }
        
        table.put_item(Item=user_item)
        return user_item

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user data"""
        table = self.dynamodb.Table(USERS_TABLE)
        
        # Build update expression
        update_expression = "SET "
        expression_attribute_values = {}
        
        for key, value in user_data.items():
            if key != 'id':  # Skip primary key
                update_expression += f"#{key} = :{key}, "
                expression_attribute_values[f":{key}"] = value
        
        # Remove trailing comma and space
        update_expression = update_expression[:-2]
        
        # Build expression attribute names
        expression_attribute_names = {f"#{key}": key for key in user_data if key != 'id'}
        
        # Update the item
        response = table.update_item(
            Key={'id': user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW"
        )
        
        return response.get('Attributes', {})

    # Bank record operations
    def create_bank_record(self, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new bank record"""
        table = self.dynamodb.Table(BANK_RECORDS_TABLE)
        record_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        record_item = {
            'id': record_id,
            'user_id': record_data['user_id'],
            'source_pdf': record_data['source_pdf'],
            'extraction_date': timestamp,
            'account_number': record_data.get('account_number'),
            'account_name': record_data.get('account_name'),
            'bank_name': record_data.get('bank_name'),
            'sort_code': record_data.get('sort_code'),
            'iban': record_data.get('iban'),
            'swift_code': record_data.get('swift_code'),
            'routing_number': record_data.get('routing_number'),
            'bsb_code': record_data.get('bsb_code'),
            'branch_code': record_data.get('branch_code'),
            'branch_address': record_data.get('branch_address'),
            'account_type': record_data.get('account_type'),
            'currency': record_data.get('currency'),
            'balance': record_data.get('balance'),
            'other_details': record_data.get('other_details')
        }
        
        table.put_item(Item=record_item)
        return record_item

    def get_bank_records_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all bank records for a user"""
        table = self.dynamodb.Table(BANK_RECORDS_TABLE)
        response = table.query(
            IndexName='user-id-index',
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        return response.get('Items', [])

    def delete_bank_records_by_user(self, user_id: str) -> int:
        """Delete all bank records for a user"""
        table = self.dynamodb.Table(BANK_RECORDS_TABLE)
        records = self.get_bank_records_by_user(user_id)
        
        count = 0
        for record in records:
            table.delete_item(Key={'id': record['id']})
            count += 1
        
        return count

    # Header config operations
    def create_header_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new header configuration"""
        table = self.dynamodb.Table(HEADER_CONFIGS_TABLE)
        config_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        config_item = {
            'id': config_id,
            'user_id': config_data['user_id'],
            'name': config_data['name'],
            'is_default': config_data.get('is_default', 0),
            'created_at': timestamp,
            'updated_at': timestamp,
            'header_mappings': config_data['header_mappings'],
            'file_format': config_data.get('file_format', 'csv')
        }
        
        table.put_item(Item=config_item)
        return config_item

    def get_header_configs_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all header configurations for a user"""
        table = self.dynamodb.Table(HEADER_CONFIGS_TABLE)
        response = table.query(
            IndexName='user-id-index',
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        return response.get('Items', [])

    def get_header_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Get header configuration by ID"""
        table = self.dynamodb.Table(HEADER_CONFIGS_TABLE)
        response = table.get_item(Key={'id': config_id})
        return response.get('Item')

    def update_header_config(self, config_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update header configuration"""
        table = self.dynamodb.Table(HEADER_CONFIGS_TABLE)
        
        # Build update expression
        update_expression = "SET updated_at = :updated_at"
        expression_attribute_values = {":updated_at": datetime.now().isoformat()}
        
        for key, value in config_data.items():
            if key not in ['id', 'user_id', 'created_at']:
                update_expression += f", #{key} = :{key}"
                expression_attribute_values[f":{key}"] = value
        
        # Build expression attribute names
        expression_attribute_names = {f"#{key}": key for key in config_data if key not in ['id', 'user_id', 'created_at']}
        
        # Update the item
        response = table.update_item(
            Key={'id': config_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW"
        )
        
        return response.get('Attributes', {})

    # Raw extraction operations
    def create_raw_extraction(self, extraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new raw extraction"""
        table = self.dynamodb.Table(RAW_EXTRACTIONS_TABLE)
        extraction_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        extraction_item = {
            'id': extraction_id,
            'user_id': extraction_data['user_id'],
            'source_pdf': extraction_data['source_pdf'],
            'extraction_date': timestamp,
            'raw_data': extraction_data.get('raw_data', {})
        }
        
        table.put_item(Item=extraction_item)
        return extraction_item

    def get_raw_extractions_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all raw extractions for a user"""
        table = self.dynamodb.Table(RAW_EXTRACTIONS_TABLE)
        response = table.query(
            IndexName='user-id-index',
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        return response.get('Items', [])

    def delete_raw_extractions_by_user(self, user_id: str) -> int:
        """Delete all raw extractions for a user"""
        table = self.dynamodb.Table(RAW_EXTRACTIONS_TABLE)
        extractions = self.get_raw_extractions_by_user(user_id)
        
        count = 0
        for extraction in extractions:
            table.delete_item(Key={'id': extraction['id']})
            count += 1
        
        return count

    # Payment operations
    def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new payment record"""
        table = self.dynamodb.Table(PAYMENTS_TABLE)
        payment_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        payment_item = {
            'id': payment_id,
            'user_id': payment_data['user_id'],
            'yativo_deposit_id': payment_data.get('yativo_deposit_id'),
            'yativo_customer_id': payment_data.get('yativo_customer_id'),
            'amount': payment_data['amount'],
            'currency': payment_data['currency'],
            'tier': payment_data['tier'],
            'payment_method': payment_data.get('payment_method'),
            'status': payment_data.get('status', 'pending'),
            'created_at': timestamp,
            'updated_at': timestamp,
            'checkout_url': payment_data.get('checkout_url')
        }
        
        table.put_item(Item=payment_item)
        return payment_item

    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by ID"""
        table = self.dynamodb.Table(PAYMENTS_TABLE)
        response = table.get_item(Key={'id': payment_id})
        return response.get('Item')

    def get_payments_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all payments for a user"""
        table = self.dynamodb.Table(PAYMENTS_TABLE)
        response = table.query(
            IndexName='user-id-index',
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        return response.get('Items', [])

    def get_payment_by_yativo_deposit_id(self, yativo_deposit_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by Yativo deposit ID"""
        table = self.dynamodb.Table(PAYMENTS_TABLE)
        response = table.query(
            IndexName='yativo-deposit-id-index',
            KeyConditionExpression=Key('yativo_deposit_id').eq(yativo_deposit_id)
        )
        items = response.get('Items', [])
        return items[0] if items else None

    def update_payment(self, payment_id: str, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update payment data"""
        table = self.dynamodb.Table(PAYMENTS_TABLE)
        
        # Build update expression
        update_expression = "SET updated_at = :updated_at"
        expression_attribute_values = {":updated_at": datetime.now().isoformat()}
        
        for key, value in payment_data.items():
            if key not in ['id', 'user_id', 'created_at']:
                update_expression += f", #{key} = :{key}"
                expression_attribute_values[f":{key}"] = value
        
        # Build expression attribute names
        expression_attribute_names = {f"#{key}": key for key in payment_data if key not in ['id', 'user_id', 'created_at']}
        
        # Update the item
        response = table.update_item(
            Key={'id': payment_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW"
        )
        
        return response.get('Attributes', {})


# Create a singleton instance
dynamodb_service = DynamoDBService()
"""
DynamoDB database operations
"""
import os
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from boto3.dynamodb.conditions import Key, Attr

from app.core.config import settings

# Table names
USERS_TABLE = settings.USERS_TABLE_NAME
HEADER_CONFIGS_TABLE = settings.HEADER_CONFIGS_TABLE_NAME
RAW_EXTRACTIONS_TABLE = settings.RAW_EXTRACTIONS_TABLE_NAME
PAYMENTS_TABLE = settings.PAYMENTS_TABLE_NAME
USER_CREDENTIALS_TABLE = settings.USER_CREDENTIALS_TABLE_NAME
API_KEYS_TABLE = settings.API_KEYS_TABLE_NAME

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
        
    def _execute_put_item(self, table_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a PutItem operation on DynamoDB
        
        Args:
            table_name: Name of the table
            item: Item to put
            
        Returns:
            The item that was put
        """
        # Process the item to ensure all values are valid for DynamoDB
        processed_item = {}
        for key, value in item.items():
            # Skip null values
            if value is None:
                continue
                
            # Convert float to Decimal
            if isinstance(value, float):
                processed_item[key] = Decimal(str(value))
            else:
                processed_item[key] = value
        
        table = self.dynamodb.Table(table_name)
        table.put_item(Item=processed_item)
        return item
    
    def _execute_get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a GetItem operation on DynamoDB
        
        Args:
            table_name: Name of the table
            key: Key to get
            
        Returns:
            The item if found, None otherwise
        """
        table = self.dynamodb.Table(table_name)
        response = table.get_item(Key=key)
        return response.get('Item')
    
    def _execute_query(self, table_name: str, index_name: Optional[str], key_condition: Key) -> List[Dict[str, Any]]:
        """Execute a Query operation on DynamoDB
        
        Args:
            table_name: Name of the table
            index_name: Name of the index to query (optional)
            key_condition: Key condition expression
            
        Returns:
            List of items matching the query
        """
        table = self.dynamodb.Table(table_name)
        
        query_args = {
            'KeyConditionExpression': key_condition
        }
        
        if index_name:
            query_args['IndexName'] = index_name
            
        response = table.query(**query_args)
        return response.get('Items', [])

    def _execute_delete_item(self, table_name: str, key: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a DeleteItem operation on DynamoDB
        
        Args:
            table_name: Name of the table
            key: Key to delete
            
        Returns:
            The deleted item
        """
        table = self.dynamodb.Table(table_name)
        response = table.delete_item(
            Key=key,
            ReturnValues="ALL_OLD"
        )
        return response.get('Attributes', {})

    def _execute_batch_delete(self, table_name: str, keys: List[Dict[str, Any]]) -> int:
        """Execute a BatchWriteItem operation to delete multiple items
        
        Args:
            table_name: Name of the table
            keys: List of keys to delete
            
        Returns:
            Number of items deleted
        """
        if not keys:
            return 0
            
        # DynamoDB BatchWriteItem can only process 25 items at a time
        batch_size = 25
        deleted_count = 0
        
        # Process in batches of 25
        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]
            request_items = {
                table_name: [
                    {
                        'DeleteRequest': {
                            'Key': key
                        }
                    } for key in batch_keys
                ]
            }
            
            # Execute the batch delete
            self.dynamodb.batch_write_item(RequestItems=request_items)
            deleted_count += len(batch_keys)
            
        return deleted_count

    # User operations
    def _build_get_user_by_id_input(self, user_id: str) -> Dict[str, Any]:
        """Build input for getting a user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            Key for the GetItem operation
        """
        return {'id': user_id}

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        key = self._build_get_user_by_id_input(user_id)
        return self._execute_get_item(USERS_TABLE, key)

    def _build_get_user_by_email_query(self, email: str) -> Key:
        """Build query for getting a user by email
        
        Args:
            email: User email
            
        Returns:
            Key condition for the Query operation
        """
        return Key('email').eq(email)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        key_condition = self._build_get_user_by_email_query(email)
        items = self._execute_query(USERS_TABLE, 'email-index', key_condition)
        return items[0] if items else None

    def _build_get_user_by_google_id_query(self, google_id: str) -> Key:
        """Build query for getting a user by Google ID
        
        Args:
            google_id: Google ID
            
        Returns:
            Key condition for the Query operation
        """
        return Key('google_id').eq(google_id)

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Google ID"""
        key_condition = self._build_get_user_by_google_id_query(google_id)
        items = self._execute_query(USERS_TABLE, 'google-id-index', key_condition)
        return items[0] if items else None

    def _build_create_user_item(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build item for creating a new user
        
        Args:
            user_data: User data
            
        Returns:
            Item for the PutItem operation
        """
        user_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        return {
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

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        user_item = self._build_create_user_item(user_data)
        return self._execute_put_item(USERS_TABLE, user_item)

    def _execute_update_item(self, table_name: str, key: Dict[str, Any], update_expression: str, 
                            expression_values: Dict[str, Any], expression_names: Dict[str, str]) -> Dict[str, Any]:
        """Execute an UpdateItem operation on DynamoDB
        
        Args:
            table_name: Name of the table
            key: Key to update
            update_expression: Update expression
            expression_values: Expression attribute values
            expression_names: Expression attribute names
            
        Returns:
            The updated item
        """
        table = self.dynamodb.Table(table_name)
        response = table.update_item(
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names,
            ReturnValues="ALL_NEW"
        )
        return response.get('Attributes', {})

    def _build_update_user_input(self, user_id: str, user_data: Dict[str, Any]) -> tuple:
        """Build input for updating a user
        
        Args:
            user_id: User ID
            user_data: User data to update
            
        Returns:
            Tuple of (key, update_expression, expression_values, expression_names)
        """
        key = {'id': user_id}
        
        # Build update expression
        update_expression = "SET "
        expression_values = {}
        expression_names = {}
        
        for key_name, value in user_data.items():
            if key_name != 'id':  # Skip primary key
                update_expression += f"#{key_name} = :{key_name}, "
                expression_values[f":{key_name}"] = value
                expression_names[f"#{key_name}"] = key_name
        
        # Remove trailing comma and space
        update_expression = update_expression[:-2]
        
        return key, update_expression, expression_values, expression_names

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user data"""
        key, update_expression, expression_values, expression_names = self._build_update_user_input(user_id, user_data)
        return self._execute_update_item(USERS_TABLE, key, update_expression, expression_values, expression_names)


    def _build_get_records_by_user_query(self, user_id: str) -> Key:
        """Build query for getting bank records by user ID
        
        Args:
            user_id: User ID
            
        Returns:
            Key condition for the Query operation
        """
        return Key('user_id').eq(user_id)

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
        
        return self._execute_put_item(HEADER_CONFIGS_TABLE, config_item)

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
        
    def delete_header_config(self, config_id: str) -> int:
        """Delete header configuration
        
        Args:
            config_id: Configuration ID
            
        Returns:
            1 if deleted, 0 if not found
        """
        # First check if the config exists
        config = self.get_header_config(config_id)
        if not config:
            return 0
            
        # Delete the config
        result = self._execute_delete_item(HEADER_CONFIGS_TABLE, {'id': config_id})
        
        # Return 1 if deleted successfully, 0 otherwise
        return 1 if result else 0

    # Raw extraction operations
    def create_raw_extraction(self, extraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new raw extraction"""
        table = self.dynamodb.Table(RAW_EXTRACTIONS_TABLE)
        extraction_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Convert raw_data to use Decimal for float values if needed
        raw_data = extraction_data.get('raw_json', {})
        
        extraction_item = {
            'id': extraction_id,
            'user_id': extraction_data['user_id'],
            'source_pdf': extraction_data['source_pdf'],
            'extraction_date': timestamp,
            'raw_data': raw_data
        }
        
        return self._execute_put_item(RAW_EXTRACTIONS_TABLE, extraction_item)

    def get_raw_extractions_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all raw extractions for a user"""
        table = self.dynamodb.Table(RAW_EXTRACTIONS_TABLE)
        response = table.query(
            IndexName='user-id-index',
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        return response.get('Items', [])
        
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the database
        
        Returns:
            List of all users
        """
        table = self.dynamodb.Table(USERS_TABLE)
        response = table.scan()
        return response.get('Items', [])

    def delete_raw_extractions_by_user(self, user_id: str) -> int:
        """Delete all raw extractions for a user"""
        # First get all extractions for the user
        extractions = self.get_raw_extractions_by_user(user_id)
        
        if not extractions:
            return 0
            
        # Extract the keys (id) from each extraction
        keys = []
        for extraction in extractions:
            if 'id' in extraction:
                keys.append({'id': extraction['id']})
        
        if not keys:
            return 0
            
        # Execute batch delete
        return self._execute_batch_delete(RAW_EXTRACTIONS_TABLE, keys)

    # Payment operations
    def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new payment record"""
        table = self.dynamodb.Table(PAYMENTS_TABLE)
        payment_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Ensure amount is a Decimal
        amount = payment_data['amount']
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        payment_item = {
            'id': payment_id,
            'user_id': payment_data['user_id'],
            'amount': amount,
            'currency': payment_data['currency'],
            'tier': payment_data['tier'],
            'status': payment_data.get('status', 'pending'),
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # Add optional fields only if they have values
        if payment_data.get('yativo_deposit_id'):
            payment_item['yativo_deposit_id'] = payment_data['yativo_deposit_id']
        
        if payment_data.get('yativo_customer_id'):
            payment_item['yativo_customer_id'] = payment_data['yativo_customer_id']
            
        if payment_data.get('payment_method'):
            payment_item['payment_method'] = payment_data['payment_method']
            
        if payment_data.get('checkout_url'):
            payment_item['checkout_url'] = payment_data['checkout_url']
        
        return self._execute_put_item(PAYMENTS_TABLE, payment_item)

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
        expression_attribute_names = {}
        
        # Process each field, ensuring correct types
        for key, value in payment_data.items():
            if key not in ['id', 'user_id', 'created_at']:
                # Skip null values
                if value is None:
                    continue
                    
                # Handle amount specifically to ensure it's a Decimal
                if key == 'amount' and not isinstance(value, Decimal):
                    value = Decimal(str(value))
                
                update_expression += f", #{key} = :{key}"
                expression_attribute_values[f":{key}"] = value
                expression_attribute_names[f"#{key}"] = key
        
        # Update the item
        response = table.update_item(
            Key={'id': payment_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW"
        )
        
        return response.get('Attributes', {})

    # User credentials operations
    def _build_store_user_credentials_item(self, user_id: str, credential_type: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Build item for storing user credentials
        
        Args:
            user_id: User ID
            credential_type: Type of credential (e.g., 'google_drive')
            credentials: Credential data
            
        Returns:
            Item for the PutItem operation
        """
        timestamp = datetime.now().isoformat()
        
        return {
            'user_id': str(user_id),
            'credential_type': credential_type,
            'credentials': credentials,
            'created_at': timestamp,
            'updated_at': timestamp
        }
    
    def store_user_credentials(self, user_id: str, credential_type: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Store user credentials
        
        Args:
            user_id: User ID
            credential_type: Type of credential (e.g., 'google_drive')
            credentials: Credential data
            
        Returns:
            The stored credentials item
        """
        item = self._build_store_user_credentials_item(user_id, credential_type, credentials)
        return self._execute_put_item(USER_CREDENTIALS_TABLE, item)
    
    def _build_get_user_credentials_key(self, user_id: str, credential_type: str) -> Dict[str, Any]:
        """Build key for getting user credentials
        
        Args:
            user_id: User ID
            credential_type: Type of credential
            
        Returns:
            Key for the GetItem operation
        """
        return {
            'user_id': str(user_id),
            'credential_type': credential_type
        }
    
    def get_user_credentials(self, user_id: str, credential_type: str) -> Optional[Dict[str, Any]]:
        """Get user credentials
        
        Args:
            user_id: User ID
            credential_type: Type of credential
            
        Returns:
            The credentials if found, None otherwise
        """
        key = self._build_get_user_credentials_key(user_id, credential_type)
        return self._execute_get_item(USER_CREDENTIALS_TABLE, key)
    
    def delete_user_credentials(self, user_id: str, credential_type: str) -> Dict[str, Any]:
        """Delete user credentials
        
        Args:
            user_id: User ID
            credential_type: Type of credential
            
        Returns:
            The deleted credentials
        """
        key = self._build_get_user_credentials_key(user_id, credential_type)
        return self._execute_delete_item(USER_CREDENTIALS_TABLE, key)

    # API Keys operations
    def create_api_key(self, user_id: str) -> Dict[str, Any]:
        """Create a new API key for a user
        
        Args:
            user_id: User ID
            
        Returns:
            The created API key item
        """
        api_key = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        api_key_item = {
            'api_key': api_key,
            'user_id': user_id,
            'status': 'active',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        return self._execute_put_item(API_KEYS_TABLE, api_key_item)
    
    def update_api_key_status(self, api_key: str, status: str) -> Dict[str, Any]:
        """Update API key status
        
        Args:
            api_key: The API key to update
            status: New status ('active' or 'inactive')
            
        Returns:
            The updated API key item
        """
        table = self.dynamodb.Table(API_KEYS_TABLE)
        timestamp = datetime.now().isoformat()
        
        response = table.update_item(
            Key={'api_key': api_key},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': status,
                ':updated_at': timestamp
            },
            ReturnValues="ALL_NEW"
        )
        
        return response.get('Attributes', {})
    
    def get_api_keys_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all API keys for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of API keys for the user
        """
        key_condition = Key('user_id').eq(user_id)
        return self._execute_query(API_KEYS_TABLE, 'user-id-index', key_condition)
    
    def get_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get API key by its value
        
        Args:
            api_key: The API key to retrieve
            
        Returns:
            The API key item if found, None otherwise
        """
        return self._execute_get_item(API_KEYS_TABLE, {'api_key': api_key})

    def set_inactive_on_user_id(self, user_id: str):
        """Set all API keys for a user to inactive
        
        Args:
            user_id: User ID
        """
        table = self.dynamodb.Table(API_KEYS_TABLE)
        table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={':status': 'inactive'}
        )

# Create a singleton instance
dynamodb_service = DynamoDBService()
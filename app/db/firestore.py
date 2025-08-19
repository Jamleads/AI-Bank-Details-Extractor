"""
Firestore database operations using Application Default Credentials (ADC)

This service automatically uses ADC for authentication:
- Service account from GOOGLE_APPLICATION_CREDENTIALS environment variable
- Default service account when running on GCP (Cloud Run, App Engine, etc.)
- User credentials from 'gcloud auth application-default login'

No project ID configuration required - ADC handles everything!
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from google.cloud import firestore
from google.api_core import exceptions

from app.core.config import settings

# Setup Firestore service logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Collection names - equivalent to DynamoDB table names
USERS_COLLECTION = "users"
HEADER_CONFIGS_COLLECTION = "header_configs"
RAW_EXTRACTIONS_COLLECTION = "raw_extractions"
PAYMENTS_COLLECTION = "payments"
USER_CREDENTIALS_COLLECTION = "user_credentials"
API_KEYS_COLLECTION = "api_keys"
PRICING_ACTIONS_COLLECTION = "pricing_actions"


class FirestoreService:
    """Firestore service for database operations"""

    def __init__(self):
        """Initialize Firestore service"""
        logger.info("Initializing Firestore service")
        try:
            # Initialize Firestore client using Application Default Credentials (ADC)
            # ADC will automatically detect:
            # - Service account from GOOGLE_APPLICATION_CREDENTIALS environment variable
            # - Default service account when running on GCP (Cloud Run, App Engine, etc.)
            # - User credentials from 'gcloud auth application-default login'
            
            self.db = firestore.Client()
            logger.info("Firestore service initialized successfully using Application Default Credentials")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {str(e)}")
            logger.error("Make sure GOOGLE_APPLICATION_CREDENTIALS is set or ADC is configured")
            raise

    def _add_timestamps(self, data: Dict[str, Any], update: bool = False) -> Dict[str, Any]:
        """Add timestamps to data"""
        now = datetime.now().isoformat()
        if not update:
            data['created_at'] = now
        data['updated_at'] = now
        return data

    def _execute_create(self, collection: str, data: Dict[str, Any], doc_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a document in a collection"""
        try:
            # Generate ID if not provided
            if not doc_id:
                doc_id = str(uuid.uuid4())
            
            # Add the ID to the data
            data['id'] = doc_id
            
            # Add timestamps
            data = self._add_timestamps(data)
            
            # Create the document
            doc_ref = self.db.collection(collection).document(doc_id)
            doc_ref.set(data)
            
            logger.debug(f"Created document in {collection}: {doc_id}")
            return data
        except Exception as e:
            logger.error(f"Error creating document in {collection}: {str(e)}")
            raise

    def _execute_get(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document from a collection"""
        try:
            doc_ref = self.db.collection(collection).document(doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting document {doc_id} from {collection}: {str(e)}")
            raise

    def _execute_query(self, collection: str, field: str, operation: str, value: Any) -> List[Dict[str, Any]]:
        """Execute a query on a collection"""
        try:
            query = self.db.collection(collection).where(field, operation, value)
            docs = query.stream()
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                results.append(data)
            
            return results
        except Exception as e:
            logger.error(f"Error querying {collection} where {field} {operation} {value}: {str(e)}")
            raise

    def _execute_update(self, collection: str, doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a document in a collection"""
        try:
            # Add updated timestamp
            data = self._add_timestamps(data, update=True)
            
            doc_ref = self.db.collection(collection).document(doc_id)
            doc_ref.update(data)
            
            # Return the updated document
            updated_doc = doc_ref.get()
            if updated_doc.exists:
                return updated_doc.to_dict()
            return data
        except Exception as e:
            logger.error(f"Error updating document {doc_id} in {collection}: {str(e)}")
            raise

    def _execute_delete(self, collection: str, doc_id: str) -> bool:
        """Delete a document from a collection"""
        try:
            doc_ref = self.db.collection(collection).document(doc_id)
            doc_ref.delete()
            logger.debug(f"Deleted document {doc_id} from {collection}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {collection}: {str(e)}")
            raise

    def _execute_batch_delete(self, collection: str, doc_ids: List[str]) -> int:
        """Delete multiple documents from a collection"""
        try:
            deleted_count = 0
            batch_size = 500  # Firestore batch limit
            
            # Process in batches
            for i in range(0, len(doc_ids), batch_size):
                batch = self.db.batch()
                batch_doc_ids = doc_ids[i:i + batch_size]
                
                for doc_id in batch_doc_ids:
                    doc_ref = self.db.collection(collection).document(doc_id)
                    batch.delete(doc_ref)
                
                batch.commit()
                deleted_count += len(batch_doc_ids)
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error batch deleting documents from {collection}: {str(e)}")
            raise

    # User operations
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        return self._execute_get(USERS_COLLECTION, user_id)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        users = self._execute_query(USERS_COLLECTION, 'email', '==', email)
        return users[0] if users else None

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Google ID"""
        users = self._execute_query(USERS_COLLECTION, 'google_id', '==', google_id)
        return users[0] if users else None

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        user_id = str(uuid.uuid4())
        
        # Prepare user data
        user_item = {
            'email': user_data['email'],
            'google_id': user_data['google_id'],
            'name': user_data.get('name'),
            'picture': user_data.get('picture'),
            'subscription_tier': user_data.get('subscription_tier', 'free'),
            'last_login': datetime.now().isoformat(),
            'subscription_updated_at': datetime.now().isoformat()
        }
        
        return self._execute_create(USERS_COLLECTION, user_item, user_id)

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user data"""
        # Remove ID from update data to avoid conflicts
        update_data = {k: v for k, v in user_data.items() if k != 'id'}
        return self._execute_update(USERS_COLLECTION, user_id, update_data)

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the database"""
        try:
            users_ref = self.db.collection(USERS_COLLECTION)
            docs = users_ref.stream()
            
            users = []
            for doc in docs:
                user_data = doc.to_dict()
                users.append(user_data)
            
            return users
        except Exception as e:
            logger.error(f"Error getting all users: {str(e)}")
            raise

    # Header config operations
    def create_header_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new header configuration"""
        config_id = str(uuid.uuid4())
        
        config_item = {
            'user_id': config_data['user_id'],
            'name': config_data['name'],
            'is_default': config_data.get('is_default', 0),
            'header_mappings': config_data['header_mappings'],
            'file_format': config_data.get('file_format', 'csv')
        }
        
        return self._execute_create(HEADER_CONFIGS_COLLECTION, config_item, config_id)

    def get_header_configs_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all header configurations for a user"""
        return self._execute_query(HEADER_CONFIGS_COLLECTION, 'user_id', '==', user_id)

    def get_header_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Get header configuration by ID"""
        return self._execute_get(HEADER_CONFIGS_COLLECTION, config_id)

    def update_header_config(self, config_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update header configuration"""
        # Remove fields that shouldn't be updated
        update_data = {k: v for k, v in config_data.items() if k not in ['id', 'user_id', 'created_at']}
        return self._execute_update(HEADER_CONFIGS_COLLECTION, config_id, update_data)

    def delete_header_config(self, config_id: str) -> int:
        """Delete header configuration"""
        try:
            # Check if config exists first
            config = self.get_header_config(config_id)
            if not config:
                return 0
            
            self._execute_delete(HEADER_CONFIGS_COLLECTION, config_id)
            return 1
        except Exception as e:
            logger.error(f"Error deleting header config {config_id}: {str(e)}")
            return 0

    # Raw extraction operations
    def create_raw_extraction(self, extraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new raw extraction"""
        extraction_id = str(uuid.uuid4())
        
        extraction_item = {
            'user_id': extraction_data['user_id'],
            'source_pdf': extraction_data['source_pdf'],
            'extraction_date': datetime.now().isoformat(),
            'raw_data': extraction_data.get('raw_json', {})
        }
        
        return self._execute_create(RAW_EXTRACTIONS_COLLECTION, extraction_item, extraction_id)

    def get_raw_extractions_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all raw extractions for a user"""
        return self._execute_query(RAW_EXTRACTIONS_COLLECTION, 'user_id', '==', user_id)

    def delete_raw_extractions_by_user(self, user_id: str) -> int:
        """Delete all raw extractions for a user"""
        try:
            # Get all extractions for the user
            extractions = self.get_raw_extractions_by_user(user_id)
            
            if not extractions:
                return 0
            
            # Extract document IDs
            doc_ids = [extraction['id'] for extraction in extractions if 'id' in extraction]
            
            if not doc_ids:
                return 0
            
            # Execute batch delete
            return self._execute_batch_delete(RAW_EXTRACTIONS_COLLECTION, doc_ids)
        except Exception as e:
            logger.error(f"Error deleting raw extractions for user {user_id}: {str(e)}")
            return 0

    # Payment operations
    def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new payment record"""
        payment_id = str(uuid.uuid4())
        
        payment_item = {
            'user_id': payment_data['user_id'],
            'amount': float(payment_data['amount']),  # Firestore handles floats natively
            'currency': payment_data['currency'],
            'tier': payment_data['tier'],
            'status': payment_data.get('status', 'pending')
        }
        
        # Add optional fields only if they have values
        optional_fields = ['yativo_deposit_id', 'yativo_customer_id', 'payment_method', 'checkout_url']
        for field in optional_fields:
            if payment_data.get(field):
                payment_item[field] = payment_data[field]
        
        return self._execute_create(PAYMENTS_COLLECTION, payment_item, payment_id)

    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by ID"""
        return self._execute_get(PAYMENTS_COLLECTION, payment_id)

    def get_payments_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all payments for a user"""
        return self._execute_query(PAYMENTS_COLLECTION, 'user_id', '==', user_id)

    def get_payment_by_yativo_deposit_id(self, yativo_deposit_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by Yativo deposit ID"""
        payments = self._execute_query(PAYMENTS_COLLECTION, 'yativo_deposit_id', '==', yativo_deposit_id)
        return payments[0] if payments else None

    def update_payment(self, payment_id: str, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update payment data"""
        # Remove fields that shouldn't be updated
        update_data = {k: v for k, v in payment_data.items() if k not in ['id', 'user_id', 'created_at']}
        
        # Handle amount conversion
        if 'amount' in update_data:
            update_data['amount'] = float(update_data['amount'])
        
        return self._execute_update(PAYMENTS_COLLECTION, payment_id, update_data)

    # User credentials operations
    def store_user_credentials(self, user_id: str, credential_type: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Store user credentials"""
        # Use composite key (user_id + credential_type) as document ID
        doc_id = f"{user_id}_{credential_type}"
        
        credential_item = {
            'user_id': str(user_id),
            'credential_type': credential_type,
            'credentials': credentials
        }
        
        return self._execute_create(USER_CREDENTIALS_COLLECTION, credential_item, doc_id)

    def get_user_credentials(self, user_id: str, credential_type: str) -> Optional[Dict[str, Any]]:
        """Get user credentials"""
        doc_id = f"{user_id}_{credential_type}"
        return self._execute_get(USER_CREDENTIALS_COLLECTION, doc_id)

    def delete_user_credentials(self, user_id: str, credential_type: str) -> Dict[str, Any]:
        """Delete user credentials"""
        doc_id = f"{user_id}_{credential_type}"
        
        # Get the document before deleting to return it
        credentials = self.get_user_credentials(user_id, credential_type)
        
        if credentials:
            self._execute_delete(USER_CREDENTIALS_COLLECTION, doc_id)
            return credentials
        
        return {}

    # API Keys operations
    def create_api_key(self, user_id: str) -> Dict[str, Any]:
        """Create a new API key for a user"""
        api_key = str(uuid.uuid4())
        
        api_key_item = {
            'api_key': api_key,
            'user_id': user_id,
            'status': 'active'
        }
        
        # Use the API key itself as the document ID for easy retrieval
        return self._execute_create(API_KEYS_COLLECTION, api_key_item, api_key)

    def update_api_key_status(self, api_key: str, status: str) -> Dict[str, Any]:
        """Update API key status"""
        return self._execute_update(API_KEYS_COLLECTION, api_key, {'status': status})

    def get_api_keys_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all API keys for a user"""
        return self._execute_query(API_KEYS_COLLECTION, 'user_id', '==', user_id)

    def get_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get API key by its value"""
        return self._execute_get(API_KEYS_COLLECTION, api_key)

    def set_inactive_on_user_id(self, user_id: str):
        """Set all API keys for a user to inactive"""
        try:
            api_keys = self.get_api_keys_by_user(user_id)
            
            # Update each API key to inactive
            for api_key_data in api_keys:
                api_key = api_key_data.get('api_key')
                if api_key:
                    self.update_api_key_status(api_key, 'inactive')
        except Exception as e:
            logger.error(f"Error setting API keys inactive for user {user_id}: {str(e)}")
            raise

    # Pricing Actions operations
    def create_pricing_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new pricing action record"""
        action_id = str(uuid.uuid4())
        
        action_item = {
            'user_id': action_data['user_id'],
            'user_email': action_data['user_email'],
            'pricing_tier': action_data['pricing_tier'],
            'price': float(action_data['price']),
            'timestamp': datetime.now().isoformat(),
            'user_name': action_data.get('user_name', ''),
            'user_subscription_tier': action_data.get('user_subscription_tier', 'FREE'),
            'ip_address': action_data.get('ip_address', ''),
            'user_agent': action_data.get('user_agent', '')
        }
        
        return self._execute_create(PRICING_ACTIONS_COLLECTION, action_item, action_id)

    def get_pricing_actions_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all pricing actions for a user"""
        try:
            # Get actions and sort by timestamp descending
            actions = self._execute_query(PRICING_ACTIONS_COLLECTION, 'user_id', '==', user_id)
            actions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return actions
        except Exception as e:
            logger.error(f"Error getting pricing actions for user {user_id}: {str(e)}")
            raise

    def get_all_pricing_actions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all pricing actions across all users"""
        try:
            actions_ref = self.db.collection(PRICING_ACTIONS_COLLECTION).limit(limit)
            docs = actions_ref.stream()
            
            actions = []
            for doc in docs:
                action_data = doc.to_dict()
                actions.append(action_data)
            
            # Sort by timestamp descending
            actions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return actions
        except Exception as e:
            logger.error(f"Error getting all pricing actions: {str(e)}")
            raise

    def get_pricing_actions_stats(self) -> Dict[str, Any]:
        """Get pricing actions statistics"""
        try:
            actions_ref = self.db.collection(PRICING_ACTIONS_COLLECTION)
            docs = actions_ref.stream()
            
            actions = []
            for doc in docs:
                action_data = doc.to_dict()
                actions.append(action_data)
            
            total_actions = len(actions)
            tier_counts = {}
            unique_users = set()
            
            for action in actions:
                tier = action.get('pricing_tier', 'unknown')
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                unique_users.add(action.get('user_id'))
            
            return {
                'total_actions': total_actions,
                'unique_users_count': len(unique_users),
                'tier_counts': tier_counts,
                'most_clicked_tier': max(tier_counts, key=tier_counts.get) if tier_counts else None
            }
        except Exception as e:
            logger.error(f"Error getting pricing actions stats: {str(e)}")
            raise


# Create a singleton instance
firestore_service = FirestoreService()

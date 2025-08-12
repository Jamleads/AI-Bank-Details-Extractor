"""
Database adapter for switching between SQLite and DynamoDB
"""
from typing import Dict, List, Optional, Any, Union, Type, TypeVar, Generic, cast
import logging
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DatabaseAdapter:
    """Database adapter for switching between SQLite and DynamoDB"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseAdapter, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the appropriate database backend"""
        self.db_type = settings.DATABASE_TYPE
        
        if self.db_type == "sqlite":
            from app.db.database import get_db
            self._db_provider = get_db
        else:
            from app.db.dynamodb import dynamodb_service
            self._db_provider = dynamodb_service

    # User operations
    def get_user_by_email(self, email: str):
        """Get user by email"""
        if self.db_type == "sqlite":
            from app.db.models import User
            db = next(self._db_provider())
            return db.query(User).filter(User.email == email).first()
        else:
            return self._db_provider.get_user_by_email(email)

    def get_user_by_google_id(self, google_id: str):
        """Get user by Google ID"""
        if self.db_type == "sqlite":
            from app.db.models import User
            db = next(self._db_provider())
            return db.query(User).filter(User.google_id == google_id).first()
        else:
            return self._db_provider.get_user_by_google_id(google_id)

    def get_user_by_id(self, user_id: Union[int, str]):
        """Get user by ID"""
        return self._db_provider.get_user_by_id(str(user_id))

    def create_user(self, user_data: Dict[str, Any]):
        """Create a new user"""
        if self.db_type == "sqlite":
            from app.db.models import User, SubscriptionTier
            db = next(self._db_provider())
            
            # Get subscription tier, ensure it's uppercase if it's a string
            subscription_tier = user_data.get("subscription_tier", SubscriptionTier.FREE)
            if isinstance(subscription_tier, str):
                if subscription_tier.lower() == "free":
                    subscription_tier = SubscriptionTier.FREE
                elif subscription_tier.lower() == "basic":
                    subscription_tier = SubscriptionTier.BASIC
                elif subscription_tier.lower() == "pro":
                    subscription_tier = SubscriptionTier.PRO
                elif subscription_tier.lower() == "enterprise":
                    subscription_tier = SubscriptionTier.ENTERPRISE
            
            user = User(
                email=user_data["email"],
                google_id=user_data["google_id"],
                name=user_data.get("name"),
                picture=user_data.get("picture"),
                subscription_tier=subscription_tier,
                subscription_updated_at=datetime.now()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        else:
            return self._db_provider.create_user(user_data)

    def update_user(self, user_id: Union[int, str], user_data: Dict[str, Any]):
        """Update user data"""
        return self._db_provider.update_user(str(user_id), user_data)

    # Bank record operations
    def create_bank_record(self, record_data: Dict[str, Any]):
        """Create a new bank record"""
        # Convert user_id to string for DynamoDB
        if "user_id" in record_data and isinstance(record_data["user_id"], int):
            record_data["user_id"] = str(record_data["user_id"])
        return self._db_provider.create_bank_record(record_data)

    def get_bank_records_by_user(self, user_id: Union[int, str]):
        """Get all bank records for a user"""
        if self.db_type == "sqlite":
            from app.db.models import BankRecord
            db = next(self._db_provider())
            return db.query(BankRecord).filter(BankRecord.user_id == user_id).all()
        else:
            return self._db_provider.get_bank_records_by_user(str(user_id))

    def delete_bank_records_by_user(self, user_id: Union[int, str]):
        """Delete all bank records for a user"""
        if self.db_type == "sqlite":
            from app.db.models import BankRecord
            db = next(self._db_provider())
            result = db.query(BankRecord).filter(BankRecord.user_id == user_id).delete()
            db.commit()
            return result
        else:
            return self._db_provider.delete_bank_records_by_user(str(user_id))

    # Header config operations
    def create_header_config(self, config_data: Dict[str, Any]):
        """Create a new header configuration"""
        # Convert user_id to string for DynamoDB
        if "user_id" in config_data and isinstance(config_data["user_id"], int):
            config_data["user_id"] = str(config_data["user_id"])
        return self._db_provider.create_header_config(config_data)

    def get_header_configs_by_user(self, user_id: Union[int, str]):
        """Get all header configurations for a user"""
        if self.db_type == "sqlite":
            from app.db.models import HeaderConfig
            db = next(self._db_provider())
            return db.query(HeaderConfig).filter(HeaderConfig.user_id == user_id).all()
        else:
            return self._db_provider.get_header_configs_by_user(str(user_id))

    def get_header_config(self, config_id: Union[int, str]):
        """Get header configuration by ID"""
        return self._db_provider.get_header_config(str(config_id))

    def update_header_config(self, config_id: Union[int, str], config_data: Dict[str, Any]):
        """Update header configuration"""
        return self._db_provider.update_header_config(str(config_id), config_data)

    def delete_header_config(self, config_id: Union[int, str]):
        """Delete header configuration"""
        return self._db_provider.delete_header_config(str(config_id))

    # Raw extraction operations
    def create_raw_extraction(self, extraction_data: Dict[str, Any]):
        """Create a new raw extraction"""
        # Convert user_id to string for DynamoDB
        if "user_id" in extraction_data and isinstance(extraction_data["user_id"], int):
            extraction_data["user_id"] = str(extraction_data["user_id"])
        return self._db_provider.create_raw_extraction(extraction_data)

    def get_raw_extractions_by_user(self, user_id: Union[int, str]):
        """Get all raw extractions for a user"""
        return self._db_provider.get_raw_extractions_by_user(str(user_id))

    def delete_raw_extractions_by_user(self, user_id: Union[int, str]):
        """Delete all raw extractions for a user"""
        return self._db_provider.delete_raw_extractions_by_user(str(user_id))

    # Payment operations
    def create_payment(self, user_id: Union[int, str], amount: float, currency: str, tier: str):
        """Create a new payment record"""
        # Create a payment data dictionary for DynamoDB
        payment_data = {
            'user_id': str(user_id),
            'amount': amount,
            'currency': currency,
            'tier': tier,
            'status': 'pending'
        }
        return self._db_provider.create_payment(payment_data)

    def get_payment(self, payment_id: Union[int, str]):
        """Get payment by ID"""
        return self._db_provider.get_payment(str(payment_id))

    def get_payments_by_user(self, user_id: Union[int, str]):
        """Get all payments for a user"""
        return self._db_provider.get_payments_by_user(str(user_id))

    def get_payment_by_yativo_deposit_id(self, yativo_deposit_id: str):
        """Get payment by Yativo deposit ID"""
        return self._db_provider.get_payment_by_yativo_deposit_id(yativo_deposit_id)

    def update_payment_status(self, payment_id: Union[int, str], status: str):
        """Update payment status"""
        # Create a payment data dictionary for DynamoDB
        payment_data = {'status': status}
        return self._db_provider.update_payment(str(payment_id), payment_data)

    def update_payment_yativo_details(
        self, 
        payment_id: Union[int, str], 
        yativo_deposit_id: str, 
        yativo_customer_id: Optional[str] = None,
        checkout_url: Optional[str] = None,
        payment_method: Optional[str] = None
    ):
        """Update payment with Yativo details"""
            # Create a payment data dictionary for DynamoDB
        payment_data = {
            'yativo_deposit_id': yativo_deposit_id
        }
        
        if yativo_customer_id:
            payment_data['yativo_customer_id'] = yativo_customer_id
        if checkout_url:
            payment_data['checkout_url'] = checkout_url
        if payment_method:
            payment_data['payment_method'] = payment_method
            
        return self._db_provider.update_payment(str(payment_id), payment_data)

    # User credentials operations
    def store_user_credentials(self, user_id: Union[int, str], credential_type: str, credentials: Dict[str, Any]):
        """Store user credentials"""
        # Convert user_id to string for DynamoDB
        if isinstance(user_id, int):
            user_id = str(user_id)
        return self._db_provider.store_user_credentials(user_id, credential_type, credentials)

    def get_user_credentials(self, user_id: Union[int, str], credential_type: str):
        """Get user credentials"""
        if self.db_type == "sqlite":
            # For SQLite, we would need to create a model and table for credentials
            # For now, we'll just log a warning and use DynamoDB
            logger.warning("Getting credentials from SQLite is not implemented, using DynamoDB instead")
            from app.db.dynamodb import dynamodb_service
            if isinstance(user_id, int):
                user_id = str(user_id)
            return dynamodb_service.get_user_credentials(user_id, credential_type)
        else:
            # Convert user_id to string for DynamoDB
            if isinstance(user_id, int):
                user_id = str(user_id)
            return self._db_provider.get_user_credentials(user_id, credential_type)

    def delete_user_credentials(self, user_id: Union[int, str], credential_type: str):
        """Delete user credentials"""
        # Convert user_id to string for DynamoDB
        if isinstance(user_id, int):
            user_id = str(user_id)
        return self._db_provider.delete_user_credentials(user_id, credential_type)

    # API Keys operations
    def create_api_key(self, user_id: str):
        """Create a new API key for a user"""
        return self._db_provider.create_api_key(user_id)

    def update_api_key_status(self, api_key: str, status: str):
        """Update the status of an API key"""
        return self._db_provider.update_api_key_status(api_key, status)

    def get_api_key_by_user_id(self, user_id: str):
        """Get an API key by user ID"""
        return self._db_provider.get_api_keys_by_user(user_id)

    def get_api_key(self, api_key: str):
        """Get an API key by API key"""
        return self._db_provider.get_api_key(api_key)

    def set_inactive_on_user_id(self, user_id: str):
        """Set all API keys for a user to inactive"""
        return self._db_provider.set_inactive_on_user_id(user_id)

    # Pricing Actions operations
    def create_pricing_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new pricing action record"""
        return self._db_provider.create_pricing_action(action_data)

    def get_pricing_actions_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all pricing actions for a user"""
        return self._db_provider.get_pricing_actions_by_user(user_id)

    def get_all_pricing_actions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all pricing actions across all users"""
        return self._db_provider.get_all_pricing_actions(limit)

    def get_pricing_actions_stats(self) -> Dict[str, Any]:
        """Get pricing actions statistics"""
        return self._db_provider.get_pricing_actions_stats()

# Create a singleton instance
db = DatabaseAdapter()
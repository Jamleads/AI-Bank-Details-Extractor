"""
Yativo payment service
"""
import os
from typing import Dict, List, Optional, Any
import requests
from fastapi import HTTPException

# These would be set from environment variables in production
YATIVO_SECRET_KEY = os.getenv("YATIVO_SECRET_KEY", "your_secret_key_here")
YATIVO_BASE_URL = os.getenv("YATIVO_BASE_URL", "https://sandbox.yativo.com")  # Use sandbox by default


class YativoService:
    """Service for interacting with Yativo API"""
    
    def __init__(self):
        """Initialize Yativo service"""
        self.base_url = YATIVO_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {YATIVO_SECRET_KEY}",
            "Content-Type": "application/json"
        }
    
    def get_payin_currencies(self, country_code: str) -> List[str]:
        """Get supported deposit currencies for a given country"""
        url = f"{self.base_url}/api/v1/payment-methods/payin/currency?country={country_code}"
        response = self._make_request("GET", url)
        return response.get("data", [])
    
    def get_payin_gateways(self, country_code: str, currency: str) -> List[Dict[str, Any]]:
        """Get available payment gateways for the specified country and currency"""
        url = f"{self.base_url}/api/v1/payment-methods/payin?country={country_code}&currency={currency}"
        response = self._make_request("GET", url)
        return response.get("data", [])
    
    def create_deposit(
        self,
        amount: float,
        currency: str,
        gateway_id: int,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new deposit (pay-in) transaction"""
        url = f"{self.base_url}/api/v1/wallet/deposits/new"
        payload = {
            "gateway": gateway_id,
            "amount": amount,
            "currency": currency
        }
        if customer_id:
            payload["customer_id"] = customer_id
        
        response = self._make_request("POST", url, json=payload)
        return response.get("data", {})
    
    def create_customer(self, user_id: str, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new customer in Yativo"""
        url = f"{self.base_url}/api/v1/customers"
        payload = {
            "external_id": str(user_id),
            "email": email
        }
        if name:
            payload["name"] = name
        
        response = self._make_request("POST", url, json=payload)
        return response.get("data", {})
    
    def register_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Register webhook URL with Yativo"""
        url = f"{self.base_url}/api/v1/business/webhook"
        payload = {"url": webhook_url}
        response = self._make_request("POST", url, json=payload)
        return response.get("data", {})
    
    def get_transaction(self, deposit_id: str) -> Dict[str, Any]:
        """Get transaction details"""
        url = f"{self.base_url}/api/v1/transactions/{deposit_id}"
        response = self._make_request("GET", url)
        return response.get("data", {})
    
    def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Yativo API"""
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Yativo API error: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    if "message" in error_data:
                        error_msg = f"Yativo API error: {error_data['message']}"
                except ValueError:
                    pass
            raise HTTPException(status_code=500, detail=error_msg)


# Create a singleton instance
yativo_service = YativoService() 
"""
Yativo payment service
"""
import os
import json
from typing import Dict, List, Optional, Any
import requests
from fastapi import HTTPException
from app.core.config import settings

# Use settings from config
YATIVO_SECRET_KEY = settings.YATIVO_SECRET_KEY
# Fix the base URL by removing any trailing spaces
YATIVO_BASE_URL = settings.YATIVO_BASE_URL.strip()

# Public key hardcoded for now - we'll use it directly in the headers
# This is a workaround for the environment variable loading issue
YATIVO_PUBLIC_KEY = "bWljaGFlbEB5YXRpdm8uY29t"


class YativoService:
    """Service for interacting with Yativo API"""
    
    def __init__(self):
        """Initialize Yativo service"""
        self.base_url = YATIVO_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {YATIVO_SECRET_KEY}",
            "Content-Type": "application/json",
            "X-Public-Key": YATIVO_PUBLIC_KEY
        }
        print(f"Initialized Yativo service with base URL: {self.base_url}")
    
    async def get_payin_currencies(self, country_code: str) -> List[str]:
        """Get supported deposit currencies for a given country"""
        url = f"{self.base_url}/api/v1/payment-methods/payin/currency?country={country_code}"
        print(f"Calling Yativo API: GET {url}")
        response = await self._make_request("GET", url)
        return response.get("data", [])
    
    async def get_payin_gateways(self, country_code: str, currency: str) -> List[Dict[str, Any]]:
        """Get available payment gateways for the specified country and currency"""
        url = f"{self.base_url}/api/v1/payment-methods/payin?country={country_code}&currency={currency}"
        print(f"Calling Yativo API: GET {url}")
        response = await self._make_request("GET", url)
        return response.get("data", [])
    
    async def create_deposit(
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
        
        print(f"Calling Yativo API: POST {url}")
        print(f"Payload: {json.dumps(payload)}")
        response = await self._make_request("POST", url, json=payload)
        return response.get("data", {})
    
    async def create_customer(self, user_id: str, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new customer in Yativo"""
        url = f"{self.base_url}/api/v1/customers"
        payload = {
            "external_id": str(user_id),
            "email": email
        }
        if name:
            payload["name"] = name
        
        print(f"Calling Yativo API: POST {url}")
        print(f"Payload: {json.dumps(payload)}")
        response = await self._make_request("POST", url, json=payload)
        return response.get("data", {})
    
    async def register_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Register webhook URL with Yativo"""
        url = f"{self.base_url}/api/v1/business/webhook"
        payload = {"url": webhook_url}
        print(f"Calling Yativo API: POST {url}")
        print(f"Payload: {json.dumps(payload)}")
        response = await self._make_request("POST", url, json=payload)
        return response.get("data", {})
    
    async def get_transaction(self, deposit_id: str) -> Dict[str, Any]:
        """Get transaction details"""
        url = f"{self.base_url}/api/v1/transactions/{deposit_id}"
        print(f"Calling Yativo API: GET {url}")
        response = await self._make_request("GET", url)
        return response.get("data", {})
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Yativo API"""
        try:
            print(f"Making {method} request to {url}")
            print(f"Headers: {self.headers}")
            if 'json' in kwargs:
                print(f"Request payload: {kwargs['json']}")
                
            response = requests.request(method, url, headers=self.headers, **kwargs)
            print(f"Response status code: {response.status_code}")
            
            # Print response content for debugging
            try:
                response_json = response.json()
                print(f"Response content: {json.dumps(response_json)}")
            except:
                print(f"Response content (not JSON): {response.text[:200]}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Yativo API error: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    print(f"Error response: {json.dumps(error_data)}")
                    if "message" in error_data:
                        error_msg = f"Yativo API error: {error_data['message']}"
                except ValueError:
                    print(f"Error response (not JSON): {e.response.text[:200]}")
            print(f"Request failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)


# Create a singleton instance
yativo_service = YativoService() 
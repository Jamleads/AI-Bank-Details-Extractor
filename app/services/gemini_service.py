"""
Service for interacting with Google Gemini AI
"""
import base64
import json
import logging
import traceback
from typing import Dict, Any, List

import google.generativeai as genai
from fastapi import HTTPException

from app.core.config import settings
from app.models.bank_details import BankDetail, BankDetailResponse

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class GeminiService:
    """Service for interacting with Google Gemini AI"""
    
    def __init__(self):
        """Initialize the Gemini service with API key"""
        logger.debug("Initializing Gemini service")
        try:
            genai.configure(api_key=settings.API_KEY)
            self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
            logger.debug("Gemini service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Gemini service: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def extract_bank_details(self, pdf_data: bytes) -> List[BankDetail]:
        """
        Extract bank details from PDF using Gemini AI
        
        Args:
            pdf_data: Raw PDF file data
            
        Returns:
            List of BankDetail objects
            
        Raises:
            HTTPException: If processing fails
        """
        try:
            logger.debug(f"Extracting bank details from PDF, size: {len(pdf_data)} bytes")
            
            # Convert PDF to base64
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            logger.debug("PDF converted to base64")
            
            # Create prompt for Gemini
            prompt = self._create_prompt()
            logger.debug("Prompt created")
            
            # Create the PDF part for the request
            pdf_part = {
                "mime_type": "application/pdf",
                "data": pdf_data
            }
            logger.debug("PDF part created for request")
            
            # Generate content with both text prompt and PDF
            logger.debug("Calling Gemini API...")
            response = self.model.generate_content([prompt, pdf_part])
            logger.debug("Received response from Gemini API")
            
            # Check if the response was blocked or had issues
            if response.candidates and response.candidates[0].finish_reason == "SAFETY":
                logger.warning("Gemini response was blocked due to safety concerns")
                raise HTTPException(status_code=400, detail="Content was blocked due to safety concerns")
            
            if not response.text:
                logger.warning("No text response received from Gemini")
                raise HTTPException(status_code=500, detail="No text response received from Gemini")
            
            # Parse the response
            logger.debug(f"Parsing response text of length: {len(response.text)}")
            bank_details = self._parse_response(response.text)
            logger.debug(f"Parsed {len(bank_details)} bank details from response")
            return bank_details
            
        except HTTPException as he:
            # Re-raise HTTP exceptions
            logger.error(f"HTTP Exception in extract_bank_details: {str(he)}")
            raise
        except Exception as e:
            logger.error(f"Error in extract_bank_details: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Failed to process with Gemini AI: {str(e)}")
    
    def _create_prompt(self) -> str:
        """Create the prompt for Gemini AI"""
        logger.debug("Creating prompt for Gemini AI")
        return """
        Please analyze this PDF document and extract ALL bank-related details and financial information. 
        
        Look for and extract the following information or related if present:
        - Account Number(s) If Account Number is not available use Acc No 
        - Account Name(s)/Account Holder Name(s) If Account Name is not available use Company Name
        - Bank Name(s)
        - Sort Code(s)
        - IBAN(s)
        - Swift Code(s)/BIC Code(s)
        - Routing Number(s)
        - BSB Code(s) (Australian)
        - Branch Code(s)
        - Branch Address(es)
        - Account Type(s)
        - Currency
        - Balance(s)
        - Any other financial identifiers or banking information
        
        Please return the results in a structured JSON format like this:
        {
            "bank_details": [
                {
                    "account_number": "value or null",
                    "account_name": "value or null",
                    "bank_name": "value or null",
                    "sort_code": "value or null",
                    "iban": "value or null",
                    "swift_code": "value or null",
                    "routing_number": "value or null",
                    "bsb_code": "value or null",
                    "branch_code": "value or null",
                    "branch_address": "value or null",
                    "account_type": "value or null",
                    "currency": "value or null",
                    "balance": "value or null",
                    "other_details": "any other relevant banking information or null"
                }
            ]
        }
        
        If multiple accounts or bank details are found, include them as separate objects in the array.
        If no banking information is found, return an empty array.
        """
    
    def _parse_response(self, response_text: str) -> List[BankDetail]:
        """
        Parse Gemini's response and extract structured data
        
        Args:
            response_text: Raw text response from Gemini
            
        Returns:
            List of BankDetail objects
        """
        try:
            logger.debug("Parsing Gemini response")
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                logger.debug(f"Found JSON in response, length: {len(json_str)}")
                
                try:
                    data = json.loads(json_str)
                    logger.debug("Successfully parsed JSON")
                    
                    # Convert to Pydantic model
                    response_model = BankDetailResponse(**data)
                    logger.debug(f"Created BankDetailResponse with {len(response_model.bank_details)} details")
                    return response_model.bank_details
                except json.JSONDecodeError as jde:
                    logger.error(f"JSON decode error: {str(jde)}")
                    logger.error(f"JSON string: {json_str}")
                    return []
                except Exception as e:
                    logger.error(f"Error creating BankDetailResponse: {str(e)}")
                    logger.error(traceback.format_exc())
                    return []
            else:
                # If no JSON found, return empty list
                logger.warning("No JSON found in response")
                return []
                
        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            logger.error(traceback.format_exc())
            # Fallback: return empty list if JSON parsing fails
            return [] 
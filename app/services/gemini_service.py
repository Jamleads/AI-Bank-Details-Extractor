"""
Service for interacting with Google Gemini AI
"""
import base64
import json
import logging
import traceback
import io
import zipfile
from typing import Dict, Any, List, Optional, Tuple

import google.generativeai as genai
import httpx
import anyio
from fastapi import HTTPException
from PyPDF2 import PdfReader
from PIL import Image

from app.core.config import settings
from app.models.bank_details import BankDetail, BankDetailResponse
from app.db.models import HeaderConfig

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class GeminiService:
    """Service for interacting with Google Gemini AI"""
    
    # Shared HTTPX client across instances
    _shared_client: Optional[httpx.AsyncClient] = None
    
    def __init__(self):
        """Initialize the Gemini service with API key"""
        logger.debug("Initializing Gemini service")
        try:
            genai.configure(api_key=settings.API_KEY)
            self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
            self.api_key = settings.API_KEY
            self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            
            # Detect HTTP/2 support (h2 package)
            http2_available = False
            try:
                import h2  # noqa: F401
                http2_available = True
            except Exception:
                logger.warning("HTTP/2 not available (missing 'h2'); falling back to HTTP/1.1. Install with: pip install 'httpx[http2]' or pip install h2")
            
            # Initialize or reuse a shared AsyncClient with HTTP/2 (if available) and tuned limits
            if GeminiService._shared_client is None:
                GeminiService._shared_client = httpx.AsyncClient(
                    http2=http2_available,
                    timeout=httpx.Timeout(connect=5.0, read=55.0, write=30.0, pool=60.0),
                    limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
                    headers={"Content-Type": "application/json"},
                )
            self.client = GeminiService._shared_client
            logger.debug("Gemini service initialized successfully with shared HTTPX client")
        except Exception as e:
            logger.error(f"Error initializing Gemini service: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _validate_pdf(self, pdf_data: bytes) -> bool:
        """
        Validate that the PDF has content and is properly formatted
        
        Args:
            pdf_data: Raw PDF file data
            
        Returns:
            bool: True if PDF is valid, False otherwise
        """
        try:
            # Check if data is empty
            if not pdf_data or len(pdf_data) < 100:  # Minimum size for a valid PDF
                logger.warning("PDF data is empty or too small")
                return False
            
            # Try to open the PDF and check if it has pages
            pdf_file = io.BytesIO(pdf_data)
            pdf_reader = PdfReader(pdf_file)
            
            # Check if PDF has pages
            if len(pdf_reader.pages) == 0:
                logger.warning("PDF has no pages")
                return False
                
            # Check if at least one page has content
            has_content = False
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text and len(text.strip()) > 0:
                    has_content = True
                    break
                    
            if not has_content:
                logger.warning("PDF has no extractable text content")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error validating PDF: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _validate_image(self, image_data: bytes) -> bool:
        """
        Validate that the image is properly formatted and has content
        
        Args:
            image_data: Raw image file data
            
        Returns:
            bool: True if image is valid, False otherwise
        """
        try:
            # Check if data is empty
            if not image_data or len(image_data) < 100:  # Minimum size for a valid image
                logger.warning("Image data is empty or too small")
                return False
            
            # Try to open the image
            image_file = io.BytesIO(image_data)
            img = Image.open(image_file)
            
            # Check if image has reasonable dimensions
            width, height = img.size
            if width < 50 or height < 50:
                logger.warning(f"Image dimensions too small: {width}x{height}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error validating image: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def _validate_pdf_async(self, pdf_data: bytes) -> bool:
        """Async wrapper to offload PDF validation to a worker thread."""
        return await anyio.to_thread.run_sync(self._validate_pdf, pdf_data)

    async def _validate_image_async(self, image_data: bytes) -> bool:
        """Async wrapper to offload image validation to a worker thread."""
        return await anyio.to_thread.run_sync(self._validate_image, image_data)

    async def _b64encode_async(self, data: bytes) -> str:
        """Async wrapper to offload base64 encoding to a worker thread."""
        return await anyio.to_thread.run_sync(lambda: base64.b64encode(data).decode('utf-8'))
    
    def _validate_zip(self, zip_data: bytes) -> List[Dict[str, Any]]:
        """
        Validate that the ZIP file contains valid files and extract contents
        
        Args:
            zip_data: Raw ZIP file data
            
        Returns:
            List of dictionaries with extracted file data:
                {
                    'filename': str,
                    'data': bytes,
                    'ext': str
                }
        """
        try:
            # Check if data is empty
            if not zip_data or len(zip_data) < 100:  # Minimum size for a valid ZIP
                logger.warning("ZIP data is empty or too small")
                return []
            
            # Try to open the ZIP
            extracted_files = []
            zip_file = io.BytesIO(zip_data)
            
            with zipfile.ZipFile(zip_file) as zf:
                # Check if ZIP has files
                if len(zf.namelist()) == 0:
                    logger.warning("ZIP file is empty")
                    return []
                
                # Extract supported files (PDF, PNG, JPG, JPEG, WebP)
                for file_info in zf.infolist():
                    # Skip directories and hidden files
                    if file_info.filename.endswith('/') or file_info.filename.startswith('__MACOSX') or file_info.filename.startswith('.'):
                        continue
                    
                    # Get file extension
                    file_ext = '.' + file_info.filename.split('.')[-1].lower() if '.' in file_info.filename else ''
                    
                    # Only extract supported files
                    if file_ext in ['.pdf', '.png', '.jpg', '.jpeg', '.webp']:
                        try:
                            # Extract file data
                            file_data = zf.read(file_info.filename)
                            
                            # Validate individual file
                            is_valid = False
                            if file_ext == '.pdf':
                                is_valid = self._validate_pdf(file_data)
                            elif file_ext in ['.png', '.jpg', '.jpeg', '.webp']:
                                is_valid = self._validate_image(file_data)
                            
                            if is_valid:
                                extracted_files.append({
                                    'filename': file_info.filename,
                                    'data': file_data,
                                    'ext': file_ext
                                })
                            else:
                                logger.warning(f"File {file_info.filename} in ZIP is not valid")
                        except Exception as e:
                            logger.warning(f"Error extracting file {file_info.filename} from ZIP: {str(e)}")
                            continue
            
            # Check if we found any valid files
            if not extracted_files:
                logger.warning("ZIP file contains no valid files")
                
            return extracted_files
            
        except zipfile.BadZipFile:
            logger.error("Invalid ZIP file format")
            return []
        except Exception as e:
            logger.error(f"Error validating ZIP: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def extract_bank_details(self, file_data: bytes, file_ext: str = '.pdf', header_config: Optional[HeaderConfig] = None) -> Dict[str, Any]:
        """
        Extract bank details from PDF or image using Gemini AI
        
        Args:
            file_data: Raw file data (PDF or image)
            file_ext: File extension to determine file type (.pdf, .png, .jpg, .jpeg, .webp)
            header_config: Optional header configuration to customize extraction fields
            
        Returns:
            Dictionary containing the raw JSON data from Gemini
            
        Raises:
            HTTPException: If processing fails
        """
        try:
            logger.debug(f"Extracting bank details from file with extension {file_ext}, size: {len(file_data)} bytes")
            
            # Validate file based on type
            is_valid = False
            mime_type = ""
            
            if file_ext.lower() == '.pdf':
                is_valid = self._validate_pdf(file_data)
                mime_type = "application/pdf"
                if not is_valid:
                    raise HTTPException(
                        status_code=400, 
                        detail="Invalid PDF file: The document appears to be empty or corrupted"
                    )
            elif file_ext.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                is_valid = self._validate_image(file_data)
                if file_ext.lower() == '.png':
                    mime_type = "image/png"
                elif file_ext.lower() == '.webp':
                    mime_type = "image/webp"
                else:
                    mime_type = "image/jpeg"
                if not is_valid:
                    raise HTTPException(
                        status_code=400, 
                        detail="Invalid image file: The image appears to be empty or corrupted"
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format: {file_ext}"
                )
            
            # Create prompt for Gemini based on header configuration
            prompt = self._create_prompt(header_config)
            
            # Create the file part for the request
            file_part = {
                "mime_type": mime_type,
                "data": file_data
            }
            
            # Generate content with both text prompt and file
            logger.debug("Calling Gemini API...")
            response = self.model.generate_content([prompt, file_part])
            logger.debug("Received response from Gemini API")
            
            # Check if the response was blocked or had issues
            if response.candidates and response.candidates[0].finish_reason == "SAFETY":
                logger.warning("Gemini response was blocked due to safety concerns")
                raise HTTPException(status_code=400, detail="Content was blocked due to safety concerns")
            
            if not response.text:
                logger.warning("No text response received from Gemini")
                raise HTTPException(status_code=500, detail="No text response received from Gemini")
            
            # Parse the response
            logger.debug(f"Parsing response from Gemini (length: {len(response.text)} chars)")
            json_data = self._parse_response(response.text)
            logger.debug(f"Successfully parsed JSON response")
            return json_data
            
        except HTTPException as he:
            # Re-raise HTTP exceptions
            logger.error(f"HTTP Exception in extract_bank_details: {str(he)}")
            raise
        except Exception as e:
            logger.error(f"Error in extract_bank_details: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Failed to process with Gemini AI: {str(e)}")
    
    def _create_prompt(self, header_config: Optional[HeaderConfig] = None) -> str:
        """
        Create the prompt for Gemini AI based on header configuration
        
        Args:
            header_config: Optional header configuration to customize extraction fields
            
        Returns:
            Prompt string for Gemini AI
        """
        logger.debug("Creating prompt for Gemini AI")
    
        # If header config is provided, use it to customize the fields to extract
        if header_config and header_config["header_mappings"]:
            logger.info(f"Using custom header configuration: {header_config['name']}")
            
            # Get all fields from the header mappings without filtering
            fields_to_extract = list(header_config["header_mappings"].keys())
            logger.debug(f"Using fields from header configuration: {fields_to_extract}")
            
            # Create field descriptions for the prompt
            field_descriptions = []
            for field in fields_to_extract:
                display_name = header_config["header_mappings"].get(field, field.replace('_', ' ').title())
                field_descriptions.append(f"- {display_name}")
            
            # If no valid fields were found, use default fields
            if not field_descriptions:
                logger.warning("No fields found in header configuration, using default fields")
                return self._create_default_prompt()
            
            # Create JSON template with all the specified fields
            json_template = {
                "bank_details": [
                    {field: "value or null" for field in fields_to_extract}
                ]
            }
            # Format the JSON template as a string
            json_template_str = json.dumps(json_template, indent=4)
            
            # Create the prompt with custom fields
            return f"""
            Please analyze this document and extract ONLY the following bank-related details:
            
            {chr(10).join(field_descriptions)}
            
            Please return the results in a structured JSON format like this:
            {json_template_str}
            
            If multiple accounts or bank details are found, include them as separate objects in the array.
            If no banking information is found, return an empty array.
            """
        else:
            # Use default prompt if no header config is provided
            logger.debug("Using default prompt")
            return self._create_default_prompt()
    
    def _create_default_prompt(self) -> str:
        """Create the default prompt for Gemini AI"""
        return """
        Please analyze this document and extract ALL bank-related details and financial information. 
        
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
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Gemini's response and extract structured data
        
        Args:
            response_text: Raw text response from Gemini
            
        Returns:
            Dictionary containing the raw JSON data from Gemini
        """
        try:
            logger.debug("Parsing Gemini response")
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                logger.debug(f"Found JSON in response, length: {len(json_str)} chars")
                
                try:
                    data = json.loads(json_str)
                    logger.debug(f"Successfully parsed JSON data")
                    return data
                except json.JSONDecodeError as jde:
                    logger.error(f"JSON decode error: {str(jde)}")
                    logger.error(f"JSON string length: {len(json_str)} chars (decode failed)")
                    return {}
                except Exception as e:
                    logger.error(f"Error parsing JSON: {str(e)}")
                    logger.error(traceback.format_exc())
                    return {}
            else:
                # If no JSON found, return empty dict
                logger.warning("No JSON found in response")
                return {}
                
        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            logger.error(traceback.format_exc())
            # Fallback: return empty dict if JSON parsing fails
            return {}

    async def extract_bank_details_async(self, file_data: bytes, file_ext: str = '.pdf', header_config: Optional[HeaderConfig] = None) -> Dict[str, Any]:
        """
        Extract bank details from PDF or image using Gemini AI asynchronously
        
        Args:
            file_data: Raw file data (PDF or image)
            file_ext: File extension to determine file type (.pdf, .png, .jpg, .jpeg, .webp)
            header_config: Optional header configuration to customize extraction fields
            
        Returns:
            Dictionary containing the raw JSON data from Gemini
            
        Raises:
            HTTPException: If processing fails
        """
        try:
            logger.debug(f"Extracting bank details asynchronously from file with extension {file_ext}, size: {len(file_data)} bytes")
            
            # Validate file based on type (offload to threads)
            is_valid = False
            mime_type = ""
            
            if file_ext.lower() == '.pdf':
                is_valid = await self._validate_pdf_async(file_data)
                mime_type = "application/pdf"
                if not is_valid:
                    raise HTTPException(
                        status_code=400, 
                        detail="Invalid PDF file: The document appears to be empty or corrupted"
                    )
            elif file_ext.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                is_valid = await self._validate_image_async(file_data)
                if file_ext.lower() == '.png':
                    mime_type = "image/png"
                elif file_ext.lower() == '.webp':
                    mime_type = "image/webp"
                else:
                    mime_type = "image/jpeg"
                if not is_valid:
                    raise HTTPException(
                        status_code=400, 
                        detail="Invalid image file: The image appears to be empty or corrupted"
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format: {file_ext}"
                )
            
            # Create prompt for Gemini based on header configuration
            prompt_text = self._create_prompt(header_config)
            
            # Encode file data to base64 (offload to thread)
            encoded_file = await self._b64encode_async(file_data)
            
            # Prepare request payload
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": encoded_file
                                }
                            },
                            {
                                "text": prompt_text
                            }
                        ]
                    }
                ]
            }
            
            # Make async API call using shared client
            logger.debug("Calling Gemini API asynchronously (shared client)...")
            response = await self.client.post(
                f"{self.api_url}?key={self.api_key}",
                json=payload,
            )
            
            # Check for HTTP errors
            if response.status_code != 200:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Gemini API error: {response.text}"
                )
            
            # Parse response
            response_data = response.json()
            logger.debug("Received response from Gemini API")
            
            # Check if response contains content
            if not response_data.get("candidates"):
                logger.warning("No candidates in Gemini response")
                raise HTTPException(status_code=500, detail="No valid response received from Gemini")
            
            # Check for safety issues
            candidate = response_data["candidates"][0]
            if candidate.get("finishReason") == "SAFETY":
                logger.warning("Gemini response was blocked due to safety concerns")
                raise HTTPException(status_code=400, detail="Content was blocked due to safety concerns")
            
            # Extract text from response
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts or "text" not in parts[0]:
                logger.warning("No text in Gemini response")
                raise HTTPException(status_code=500, detail="No text response received from Gemini")
            
            response_text = parts[0]["text"]
            
            # Parse the response
            logger.debug(f"Parsing response from Gemini (length: {len(response_text)} chars)")
            json_data = self._parse_response(response_text)
            logger.debug(f"Successfully parsed JSON response")
            return json_data
                
        except HTTPException as he:
            # Re-raise HTTP exceptions
            logger.error(f"HTTP Exception in extract_bank_details_async: {str(he)}")
            raise
        except Exception as e:
            logger.error(f"Error in extract_bank_details_async: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Failed to process with Gemini AI: {str(e)}") 
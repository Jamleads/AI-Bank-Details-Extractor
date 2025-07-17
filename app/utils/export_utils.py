"""
Utility functions for exporting data to various formats
"""
import os
import csv
import json
import tempfile
import logging
from typing import List, Dict, Any, Optional, Tuple

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def generate_csv_file(
    data: List[Dict[str, Any]], 
    custom_headers: Optional[str] = None
) -> Tuple[str, str]:
    """
    Generate a CSV file from data
    
    Args:
        data: List of dictionaries containing data to export
        custom_headers: Optional comma-separated custom headers
        
    Returns:
        Tuple containing:
            - Path to the generated file
            - Filename for the download
    """
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            file_path = temp_file.name
        
        # Get all possible headers from data
        all_headers = set()
        for record in data:
            all_headers.update(record.keys())
        
        # Use custom headers if provided
        if custom_headers:
            try:
                headers = [h.strip() for h in custom_headers.split(',')]
                # Ensure all headers exist in the data
                headers = [h for h in headers if h in all_headers]
            except Exception as e:
                logger.error(f"Error parsing custom headers: {str(e)}")
                headers = sorted(all_headers)
        else:
            headers = sorted(all_headers)
        
        # Write CSV
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            
            for record in data:
                # Convert None values to empty strings and handle other types
                sanitized_record = {}
                for k, v in record.items():
                    if v is None:
                        sanitized_record[k] = ""
                    elif isinstance(v, (dict, list)):
                        sanitized_record[k] = json.dumps(v)
                    else:
                        sanitized_record[k] = str(v)
                
                writer.writerow(sanitized_record)
        
        logger.debug(f"CSV file created at {file_path}")
        return file_path, 'bank_details.csv'
    
    except Exception as e:
        logger.error(f"Error generating CSV file: {str(e)}")
        raise

def generate_json_file(data: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Generate a JSON file from data
    
    Args:
        data: List of dictionaries containing data to export
        
    Returns:
        Tuple containing:
            - Path to the generated file
            - Filename for the download
    """
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
            file_path = temp_file.name
        
        # Write JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"bank_details": data}, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"JSON file created at {file_path}")
        return file_path, 'bank_details.json'
    
    except Exception as e:
        logger.error(f"Error generating JSON file: {str(e)}")
        raise 
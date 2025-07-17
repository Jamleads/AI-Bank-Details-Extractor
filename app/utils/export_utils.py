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
        
        # Write CSV
        with open(file_path, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=all_headers, extrasaction='ignore')
            writer.writeheader()
            
            for record in data:
                writer.writerow({k: str(v) if v is not None else "" for k, v in record.items()})
        
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
        with open(file_path, 'w') as f:
            json.dump({"bank_details": data}, f, indent=2)
        
        logger.debug(f"JSON file created at {file_path}")
        return file_path, 'bank_details.json'
    
    except Exception as e:
        logger.error(f"Error generating JSON file: {str(e)}")
        raise 
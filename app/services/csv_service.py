"""
Service for handling CSV operations
"""
import csv
import os
from datetime import datetime
from typing import List, Dict, Any

from app.core.config import settings
from app.models.bank_details import BankDetail, CSVRecord


class CSVService:
    """Service for handling CSV operations"""
    
    def __init__(self):
        """Initialize the CSV service"""
        self.csv_path = settings.OUTPUT_FOLDER / "combined_bank_details.csv"
        os.makedirs(settings.OUTPUT_FOLDER, exist_ok=True)
    
    def save_bank_details(self, bank_details: List[BankDetail], source_pdf: str) -> Dict[str, Any]:
        """
        Save bank details to combined CSV file
        
        Args:
            bank_details: List of bank details to save
            source_pdf: Source PDF filename
            
        Returns:
            Dictionary with operation results
        """
        if not bank_details:
            return {
                'success': False,
                'error': "No bank details found in the response",
                'records_added': 0,
                'total_records': 0
            }
        
        # Define CSV headers based on the model
        headers = [
            'source_pdf',
            'extraction_date',
            'account_number',
            'account_name',
            'bank_name',
            'sort_code',
            'iban',
            'swift_code',
            'routing_number',
            'bsb_code',
            'branch_code',
            'branch_address',
            'account_type',
            'currency',
            'balance',
            'other_details'
        ]
        
        try:
            # Check if file exists
            file_exists = os.path.exists(self.csv_path)
            
            # Determine write mode
            mode = 'a' if file_exists else 'w'
            
            records_added = 0
            with open(self.csv_path, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                
                # Write headers only if file is new
                if not file_exists:
                    writer.writeheader()
                
                # Write records
                for record in bank_details:
                    # Convert Pydantic model to dict and add source and date
                    csv_record = CSVRecord(
                        **record.model_dump(),
                        source_pdf=source_pdf or 'Unknown',
                        extraction_date=datetime.now()
                    )
                    
                    # Write to CSV
                    writer.writerow(csv_record.model_dump())
                    records_added += 1
            
            # Count total records
            total_records = self.count_total_records()
            
            return {
                'success': True,
                'file_existed': file_exists,
                'records_added': records_added,
                'total_records': total_records,
                'filename': os.path.basename(str(self.csv_path)),
                'message': f"{'Appended' if file_exists else 'Created'} {records_added} records to combined CSV"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error saving to CSV: {str(e)}",
                'records_added': 0,
                'total_records': 0
            }
    
    def get_processed_files(self) -> List[str]:
        """
        Get list of unique PDF files that have been processed and saved to CSV
        
        Returns:
            List of unique PDF filenames
        """
        processed_files = set()
        
        if not os.path.exists(self.csv_path):
            return []
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    pdf_name = row.get('source_pdf', '').strip()
                    if pdf_name and pdf_name != 'Unknown':
                        processed_files.add(pdf_name)
        except Exception:
            return []
        
        return sorted(list(processed_files))
    
    def count_total_records(self) -> int:
        """
        Count total number of records in the CSV file
        
        Returns:
            Total number of records (excluding header)
        """
        if not os.path.exists(self.csv_path):
            return 0
            
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as csvfile:
                # Read the first line to check if there's a header
                first_line = csvfile.readline().strip()
                if not first_line:  # Empty file
                    return 0
                    
                # Count remaining lines (actual data records)
                count = 0
                for _ in csvfile:
                    count += 1
                    
                return count
        except Exception:
            return 0 
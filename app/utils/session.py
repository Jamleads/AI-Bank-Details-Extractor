"""
Session management utilities
"""
from typing import List

from app.services.csv_service import CSVService


class PDFSessionManager:
    """Manages PDF upload session data"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PDFSessionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.uploaded_files = []
        self.enable_download = False
        self.csv_service = CSVService()
        
        # Pre-populate with files from CSV
        self._load_files_from_csv()
        
        self._initialized = True
    
    def _load_files_from_csv(self):
        """Load source_pdf values from CSV file to populate the files list"""
        try:
            processed_files = self.csv_service.get_processed_files()
            for filename in processed_files:
                self.add_file(filename)
            
            # Enable download if we have records
            if len(processed_files) > 0:
                self.enable_download = True
        except Exception as e:
            print(f"Error loading files from CSV: {str(e)}")
    
    def add_file(self, filename: str):
        """Add a file to the session if not already present"""
        if filename not in self.uploaded_files:
            self.uploaded_files.append(filename)
    
    def get_files_list(self) -> List[str]:
        """Get list of files in current session"""
        return self.uploaded_files.copy()
    
    def get_files_display(self) -> str:
        """Get formatted string of files for display"""
        if not self.uploaded_files:
            return "No files selected"
        return ", ".join(self.uploaded_files)
    
    def clear_session(self):
        """Clear the current session"""
        self.uploaded_files.clear()
    
    def get_total_processed_files(self) -> List[str]:
        """Get all files that have been processed (from CSV)"""
        return self.csv_service.get_processed_files()
    
    def get_total_records(self) -> int:
        """Get total number of records in the combined CSV"""
        return self.csv_service.count_total_records()
    
    def get_session_status(self):
        """Get current session status"""
        processed_files = self.get_total_processed_files()
        total_records = self.get_total_records()
        
        return {
            'files_display': self.get_files_display(),
            'all_processed_files': processed_files,
            'session_files': self.get_files_list(),
            'total_records': total_records,
            'enable_download': self.enable_download,
            'has_files': len(self.uploaded_files) > 0
        } 
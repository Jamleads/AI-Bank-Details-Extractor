#!/usr/bin/env python3
"""
PDF Bank Details Extractor Web Application
Uploads PDF to Google Gemini AI for bank details extraction and generates CSV
"""

import os
import csv
import json
import base64
import requests
from flask import Flask, request, render_template_string, jsonify, send_file, flash
from werkzeug.utils import secure_filename
import tempfile
from datetime import datetime
import google.generativeai as genai
import base64
from typing import List, Dict, Any


app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Constants
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

# Create necessary folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bank Details Extractor</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }

        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }

        .main-content {
            padding: 40px;
        }

        .upload-section {
            border: 3px dashed #ddd;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin-bottom: 30px;
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .upload-section:hover {
            border-color: #3498db;
            background-color: #f8f9fa;
        }

        .upload-section.dragover {
            border-color: #2ecc71;
            background-color: #e8f5e9;
        }

        .upload-icon {
            font-size: 4em;
            color: #bdc3c7;
            margin-bottom: 20px;
        }

        .upload-text {
            font-size: 1.2em;
            color: #7f8c8d;
            margin-bottom: 20px;
        }

        .file-input {
            display: none;
        }

        .upload-btn {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 25px;
            font-size: 1.1em;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .upload-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(52, 152, 219, 0.4);
        }

        .status-section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 30px;
        }

        .status-title {
            font-size: 1.3em;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .files-display {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }

        .files-label {
            font-weight: 600;
            color: #495057;
            margin-bottom: 8px;
            display: block;
        }

        .files-list {
            color: #6c757d;
            font-family: 'Courier New', monospace;
            font-size: 0.95em;
            line-height: 1.4;
        }

        .files-list.has-files {
            color: #28a745;
            font-weight: 500;
        }

        .progress-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }

        .info-card {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }

        .info-number {
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
            display: block;
        }

        .info-label {
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 5px;
        }

        .results-section {
            background: #e8f5e9;
            border: 1px solid #c3e6cb;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 30px;
            display: none;
        }

        .results-section.show {
            display: block;
        }

        .results-section.error {
            background: #f8d7da;
            border-color: #f5c6cb;
        }

        .results-title {
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .results-title.success {
            color: #155724;
        }

        .results-title.error {
            color: #721c24;
        }

        .results-content {
            color: #155724;
            line-height: 1.6;
        }

        .results-content.error {
            color: #721c24;
        }

        .download-section {
            text-align: center;
            margin-top: 30px;
        }

        .download-btn {
            background: linear-gradient(135deg, #27ae60, #2ecc71);
            color: white;
            padding: 15px 40px;
            border: none;
            border-radius: 25px;
            font-size: 1.1em;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 10px;
        }

        .download-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(39, 174, 96, 0.4);
        }

        .download-btn:disabled {
            background: #bdc3c7;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .clear-btn {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white;
            padding: 10px 25px;
            border: none;
            border-radius: 20px;
            font-size: 0.9em;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-left: 15px;
        }

        .clear-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 10px rgba(231, 76, 60, 0.4);
        }

        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }

        .loading.show {
            display: block;
        }

        .spinner {
            border: 4px solid #f3f3f4;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .fade-in {
            animation: fadeIn 0.5s ease-in;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 768px) {
            .container {
                margin: 10px;
                border-radius: 10px;
            }
            
            .main-content {
                padding: 20px;
            }
            
            .progress-info {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-file-invoice-dollar"></i> Bank Details Extractor</h1>
            <p>Upload PDF documents to extract banking information automatically</p>
        </div>

        <div class="main-content">
            <!-- Upload Section -->
            <div class="upload-section" id="uploadSection">
                <div class="upload-icon">
                    <i class="fas fa-cloud-upload-alt"></i>
                </div>
                <div class="upload-text">
                    Drag & drop your PDF files here
                </div>
                <input type="file" id="fileInput" class="file-input" accept=".pdf" multiple>
                <button type="button" id="chooseFilesBtn" class="upload-btn">
                    <i class="fas fa-folder-open"></i> Choose Files
                </button>
            </div>

            <!-- Status Section -->
            <div class="status-section">
                <div class="status-title">
                    <i class="fas fa-info-circle"></i>
                    Processing Status
                </div>
                
                <div class="files-display">
                    <span class="files-label">Selected Files:</span>
                    <div class="files-list" id="filesDisplay">No files selected</div>
                </div>

                <div class="progress-info">
                    <div class="info-card">
                        <span class="info-number" id="totalRecords">0</span>
                        <div class="info-label">Total Records</div>
                    </div>
                    <div class="info-card">
                        <span class="info-number" id="totalFiles">0</span>
                        <div class="info-label">Files Processed</div>
                    </div>
                </div>

                <div style="margin-top: 15px; text-align: right;">
                    <button class="clear-btn" onclick="clearSession()">
                        <i class="fas fa-trash"></i> Clear Session
                    </button>
                </div>
            </div>

            <!-- Loading Section -->
            <div class="loading" id="loadingSection">
                <div class="spinner"></div>
                <p>Processing PDF and extracting bank details...</p>
            </div>

            <!-- Results Section -->
            <div class="results-section" id="resultsSection">
                <div class="results-title" id="resultsTitle">
                    <i class="fas fa-check-circle"></i>
                    <span id="resultsTitleText">Processing Complete</span>
                </div>
                <div class="results-content" id="resultsContent">
                    <!-- Results will be displayed here -->
                </div>
            </div>

            <!-- Download Section -->
            <div class="download-section">
                <button class="download-btn" id="downloadBtn" onclick="downloadCSV()">
                    <i class="fas fa-download"></i>
                    Download Combined CSV
                </button>
            </div>
        </div>
    </div>

    <script>
        let processedFiles = [];
        let totalRecords = 0;

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            console.log("DOM content loaded, initializing page");
            
            // First update session status to get pre-populated files
            updateSessionStatus().then(() => {
                console.log("Session status updated with pre-populated files");
                setupEventListeners();
                console.log("Event listeners set up");
            });
        });

        function setupEventListeners() {
            const uploadSection = document.getElementById('uploadSection');
            const fileInput = document.getElementById('fileInput');
            const chooseFilesBtn = document.getElementById('chooseFilesBtn');
            
            console.log("Setting up event listeners for upload section");

            // Drag and drop functionality
            uploadSection.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadSection.classList.add('dragover');
            });

            uploadSection.addEventListener('dragleave', () => {
                uploadSection.classList.remove('dragover');
            });

            uploadSection.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadSection.classList.remove('dragover');
                const files = e.dataTransfer.files;
                handleFiles(files);
            });

            // File input change
            fileInput.addEventListener('change', (e) => {
                handleFiles(e.target.files);
            });

            // Choose files button click - separate from the upload section click
            chooseFilesBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent event from bubbling up to the upload section
                fileInput.click();
            });
            
            // Remove the click handler from the upload section itself
        }

        async function handleFiles(files) {
            console.log("handleFiles called with", files.length, "files");
            
            if (!files || files.length === 0) {
                console.log("No files selected");
                return;
            }
            
            // Filter for PDF files
            const pdfFiles = Array.from(files).filter(file => {
                console.log("File:", file.name, "Type:", file.type);
                // Check both MIME type and extension for PDF
                return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
            });
            
            console.log("Filtered PDF files:", pdfFiles.length);
            
            if (pdfFiles.length === 0) {
                showResults('No PDF files selected. Please select PDF files only.', false);
                return;
            }

            for (let file of pdfFiles) {
                console.log("Processing PDF file:", file.name);
                await processFile(file);
            }
        }

        async function updateSessionStatus() {
            try {
                console.log("Fetching session status...");
                const response = await fetch('/get_session_status');
                const status = await response.json();
                
                console.log("Session status:", status);
                updateFilesList(status.files_display);
                updateCounts(status.total_records, status.all_processed_files.length);
                
                if (status.all_processed_files.length > 0) {
                    document.getElementById('downloadBtn').disabled = false;
                }
                
                return status;
            } catch (error) {
                console.error('Error updating session status:', error);
                return null;
            }
        }

        function updateFilesList(filesDisplay) {
            const filesElement = document.getElementById('filesDisplay');
            filesElement.textContent = filesDisplay;
            
            if (filesDisplay !== 'No files selected') {
                filesElement.classList.add('has-files');
            } else {
                filesElement.classList.remove('has-files');
            }
        }

        function updateCounts(records, files) {
            document.getElementById('totalRecords').textContent = records;
            document.getElementById('totalFiles').textContent = files;
        }

        async function processFile(file) {
            console.log("Processing file:", file.name);
            showLoading(true);
            hideResults();

            try {
                // Create FormData and append the file
                const formData = new FormData();
                formData.append('pdf_file', file);
                console.log("Sending request to /process endpoint with file:", file.name);

                // Send the request
                const response = await fetch('/process', {
                    method: 'POST',
                    body: formData
                });

                console.log("Response received:", response.status);
                
                // Check if response is ok
                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }
                
                // Parse the response
                const result = await response.json();
                console.log("Response data:", result);
                
                if (result.success) {
                    // Update UI with results
                    updateFilesList(result.files_display);
                    updateCounts(result.total_records, result.all_processed_files.length);
                    
                    showResults(
                        `✅ Successfully processed "${file.name}"<br>
                        📄 ${result.records_added} new records added<br>
                        📊 Total records in database: ${result.total_records}<br>
                        💾 Data has been added to existing CSV records`, 
                        true
                    );
                    
                    // Enable download button if we have records
                    if (result.enable_download) {
                        document.getElementById('downloadBtn').disabled = false;
                    }
                } else {
                    console.error("Error in response:", result.error);
                    showResults(`❌ Error processing "${file.name}": ${result.error}`, false);
                }
            } catch (error) {
                console.error("Upload failed:", error);
                showResults(`❌ Upload failed: ${error.message}`, false);
            } finally {
                showLoading(false);
            }
        }

        function showLoading(show) {
            const loadingSection = document.getElementById('loadingSection');
            if (show) {
                loadingSection.classList.add('show');
            } else {
                loadingSection.classList.remove('show');
            }
        }

        function showResults(message, isSuccess) {
            const resultsSection = document.getElementById('resultsSection');
            const resultsTitle = document.getElementById('resultsTitle');
            const resultsTitleText = document.getElementById('resultsTitleText');
            const resultsContent = document.getElementById('resultsContent');

            // Set content
            resultsContent.innerHTML = message;
            
            // Set styling based on success/error
            if (isSuccess) {
                resultsSection.classList.remove('error');
                resultsTitle.classList.remove('error');
                resultsTitle.classList.add('success');
                resultsContent.classList.remove('error');
                resultsTitle.innerHTML = '<i class="fas fa-check-circle"></i><span>Processing Complete</span>';
            } else {
                resultsSection.classList.add('error');
                resultsTitle.classList.remove('success');
                resultsTitle.classList.add('error');
                resultsContent.classList.add('error');
                resultsTitle.innerHTML = '<i class="fas fa-exclamation-circle"></i><span>Processing Error</span>';
            }

            // Show with animation
            resultsSection.classList.add('show', 'fade-in');
        }

        function hideResults() {
            const resultsSection = document.getElementById('resultsSection');
            resultsSection.classList.remove('show');
        }

        async function clearSession() {
            if (confirm('Are you sure you want to clear the current session? This will not delete the CSV file.')) {
                try {
                    const response = await fetch('/clear_session', {
                        method: 'POST'
                    });
                    
                    if (response.ok) {
                        // Reset UI
                        updateFilesList('No files selected');
                        hideResults();
                        
                        // Keep the total files count from CSV but reset session files
                        await updateSessionStatus();
                        
                        showResults('✅ Session cleared successfully. CSV file remains intact.', true);
                    }
                } catch (error) {
                    showResults('❌ Error clearing session: ' + error.message, false);
                }
            }
        }

        function downloadCSV() {
            // Use the combined CSV filename
            const filename = 'combined_bank_details.csv';
            
            // Show loading state
            showLoading(true);
            
            // Try to download the file
            fetch(`/download/${filename}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(response.statusText);
                    }
                    return response.blob();
                })
                .then(blob => {
                    // Create a download link
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                })
                .catch(error => {
                    showResults('❌ Error downloading file: ' + error.message, false);
                })
                .finally(() => {
                    showLoading(false);
                });
        }
    </script>
</body>
</html>
"""

def encode_pdf_to_base64(file_data):
    """Convert PDF file or data to base64 for Gemini API"""
    if isinstance(file_data, str):
        # If it's a file path
        with open(file_data, 'rb') as pdf_file:
            return base64.b64encode(pdf_file.read()).decode('utf-8')
    else:
        # If it's already bytes
        return base64.b64encode(file_data).decode('utf-8')


def extract_bank_details_with_gemini(pdf_base64: str) -> str:
    """
    Send PDF to Gemini AI and extract bank details using the official Google Generative AI library
    
    Args:
        pdf_base64 (str): Base64 encoded PDF data
        api_key (str): Google API key for Gemini
        
    Returns:
        str: JSON string containing extracted bank details
        
    Raises:
        Exception: If the API call fails or processing encounters an error
    """
    
    # Configure the API key
    genai.configure(api_key="")
    
    # Initialize the model
    model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
    
    prompt = """
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
    
    try:
        # Decode base64 to bytes for the PDF
        pdf_data = base64.b64decode(pdf_base64)
        
        # Create the PDF part for the request
        pdf_part = {
            "mime_type": "application/pdf",
            "data": pdf_data
        }
        
        # Generate content with both text prompt and PDF
        response = model.generate_content([prompt, pdf_part])
        
        # Check if the response was blocked or had issues
        if response.candidates and response.candidates[0].finish_reason == "SAFETY":
            raise Exception("Content was blocked due to safety concerns")
        
        if not response.text:
            raise Exception("No text response received from Gemini")
            
        return response.text
        
    except Exception as e:
        raise Exception(f"Failed to process with Gemini AI: {str(e)}")



def parse_gemini_response(response_text):
    """Parse Gemini's response and extract structured data"""
    try:
        # Try to find JSON in the response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)
            return data.get('bank_details', [])
        else:
            # If no JSON found, try to extract information manually
            return []
            
    except json.JSONDecodeError:
        # Fallback: return empty list if JSON parsing fails
        return []

def save_to_csv(bank_details: str, source_pdf: str = None) -> Dict[str, Any]:
    """
    Save bank details to combined CSV file, appending to existing file or creating new one with headers.
    """
    # Define CSV headers
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
        # Parse the JSON bank details
        data = json.loads(bank_details)
        bank_records = data.get('bank_details', [])
        
        if not bank_records:
            return {
                'success': False,
                'error': "No bank details found in the response",
                'records_added': 0,
                'total_records': 0
            }
        
        # Get the combined CSV path
        session_manager = PDFSessionManager()
        csv_path = session_manager.combined_csv
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        print(f"Saving CSV to: {csv_path}")  # Debug log
        
        # Check if file exists
        file_exists = os.path.exists(csv_path)
        
        # Determine write mode
        mode = 'a' if file_exists else 'w'
        
        records_added = 0
        with open(csv_path, mode, newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            
            # Write headers only if file is new
            if not file_exists:
                writer.writeheader()
            
            # Write records
            for record in bank_records:
                row = {
                    'source_pdf': source_pdf or 'Unknown',
                    'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'account_number': record.get('account_number'),
                    'account_name': record.get('account_name'),
                    'bank_name': record.get('bank_name'),
                    'sort_code': record.get('sort_code'),
                    'iban': record.get('iban'),
                    'swift_code': record.get('swift_code'),
                    'routing_number': record.get('routing_number'),
                    'bsb_code': record.get('bsb_code'),
                    'branch_code': record.get('branch_code'),
                    'branch_address': record.get('branch_address'),
                    'account_type': record.get('account_type'),
                    'currency': record.get('currency'),
                    'balance': record.get('balance'),
                    'other_details': record.get('other_details')
                }
                writer.writerow(row)
                records_added += 1
        
        print(f"Successfully wrote {records_added} records to CSV")  # Debug log
        
        # Count total records
        total_records = 0
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                total_records = sum(1 for row in reader) - 1  # Subtract header row
        
        return {
            'success': True,
            'file_existed': file_exists,
            'records_added': records_added,
            'total_records': total_records,
            'filename': os.path.basename(csv_path),
            'message': f"{'Appended' if file_exists else 'Created'} {records_added} records to combined CSV"
        }
        
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")  # Debug log
        return {
            'success': False,
            'error': f"Error saving to CSV: {str(e)}",
            'records_added': 0,
            'total_records': 0
        }


def get_processed_files_list(filename: str) -> List[str]:
    """
    Get list of unique PDF files that have been processed and saved to CSV.
    
    Args:
        filename (str): CSV filename to read from
        
    Returns:
        List of unique PDF filenames
    """
    processed_files = set()
    
    if not os.path.exists(filename):
        return []
    
    try:
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                pdf_name = row.get('source_pdf', '').strip()
                if pdf_name and pdf_name != 'Unknown':
                    processed_files.add(pdf_name)
    except Exception as e:
        print(f"Error reading processed files: {e}")
        return []
    
    return sorted(list(processed_files))


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
        self.combined_csv = os.path.join(OUTPUT_FOLDER, "combined_bank_details.csv")
        self.enable_download = False
        
        # Ensure output folder exists
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        
        # Pre-populate with files from CSV
        self._load_files_from_csv()
        
        self._initialized = True
    
    def _load_files_from_csv(self):
        """Load source_pdf values from CSV file to populate the files list"""
        if os.path.exists(self.combined_csv):
            try:
                processed_files = get_processed_files_list(self.combined_csv)
                for filename in processed_files:
                    self.add_file(filename)
                
                # Enable download if we have records
                if len(processed_files) > 0:
                    self.enable_download = True
                    
                print(f"Pre-populated {len(processed_files)} files from CSV")
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
        return get_processed_files_list(self.combined_csv)
    
    def get_total_records(self) -> int:
        """Get total number of records in the combined CSV"""
        if not os.path.exists(self.combined_csv):
            return 0
        try:
            with open(self.combined_csv, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                return sum(1 for row in reader) - 1  # Subtract header row
        except Exception:
            return 0


@app.route('/')
def index():
    """Main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process_pdf():
    """Process uploaded PDF file and extract bank details"""
    try:
        print("Received /process request")
        
        if 'pdf_file' not in request.files:
            print("No pdf_file in request.files")
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            
        file = request.files['pdf_file']
        if file.filename == '':
            print("Empty filename")
            return jsonify({'success': False, 'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            print(f"Invalid file type: {file.filename}")
            return jsonify({'success': False, 'error': 'Only PDF files are allowed'}), 400
            
        # Get the filename but don't save to disk
        filename = secure_filename(file.filename)
        print(f"Processing file: {filename}")
        
        # Read file content directly into memory
        file_content = file.read()
        
        # Convert to base64 directly from memory
        pdf_base64 = base64.b64encode(file_content).decode('utf-8')
        
        print("Extracting bank details with Gemini")
        response_text = extract_bank_details_with_gemini(pdf_base64)
        
        print("Parsing Gemini response")
        bank_details = parse_gemini_response(response_text)
        
        # Convert bank_details list back to JSON format expected by save_to_csv
        bank_details_json = json.dumps({"bank_details": bank_details})
        
        # Save to combined CSV
        print("Saving to CSV")
        result = save_to_csv(bank_details_json, filename)
        
        # Update session
        print("Updating session")
        session_manager = PDFSessionManager()
        session_manager.add_file(filename)
        
        # Get updated counts
        total_records = session_manager.get_total_records()
        processed_files = session_manager.get_total_processed_files()
        
        # Enable download button if we have records
        if total_records > 0:
            session_manager.enable_download = True
        
        print(f"Processing complete: {result}")
        return jsonify({
            'success': True,
            'records_added': result.get('records_added', 0),
            'total_records': total_records,
            'files_display': session_manager.get_files_display(),
            'all_processed_files': processed_files,
            'enable_download': session_manager.enable_download
        })
        
    except Exception as e:
        print(f"Error in /process: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download_csv(filename):
    """Download the CSV file"""
    try:
        # Verify file extension
        if not filename.endswith('.csv'):
            return "Invalid file format. Only CSV files are allowed.", 400
            
        # Get the absolute path to the output folder
        output_folder = os.path.abspath(OUTPUT_FOLDER)
        file_path = os.path.join(output_folder, filename)
        
        print(f"Attempting to download file from: {file_path}")  # Debug log
        
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"File not found at path: {file_path}")  # Debug log
            return "File not found.", 404
            
        # Check if file is empty
        if os.path.getsize(file_path) == 0:
            return "The CSV file is empty. Please process some PDFs first.", 400
            
        # Send the file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    except Exception as e:
        print(f"Download error: {str(e)}")  # Debug log
        return f"Download error: {str(e)}", 500

@app.route('/get_session_status')
def get_session_status():
    """Get the current session status including processed files"""
    try:
        session_manager = PDFSessionManager()
        total_records = session_manager.get_total_records()
        processed_files = session_manager.get_total_processed_files()
        
        # Get the list of files in the current session
        session_files = session_manager.get_files_list()
        
        return jsonify({
            'files_display': session_manager.get_files_display(),
            'all_processed_files': processed_files,
            'session_files': session_files,
            'total_records': total_records,
            'enable_download': session_manager.enable_download,
            'has_files': len(session_files) > 0
        })
    except Exception as e:
        print(f"Error in get_session_status: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/clear_session', methods=['POST'])
def clear_session():
    """Clear the current session"""
    try:
        session_manager = PDFSessionManager()
        session_manager.clear_session()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/check_file/<filename>')
def check_file(filename):
    """Check if a file exists"""
    try:
        if not filename.endswith('.csv'):
            return jsonify({'exists': False, 'error': 'Invalid file format'}), 400
            
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        exists = os.path.exists(file_path)
        return jsonify({'exists': exists})
    except Exception as e:
        return jsonify({'exists': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting PDF Bank Details Extractor...")
    print("Server will be available at: http://localhost:5000")
    print("\nFeatures:")
    print("- Upload PDF files")
    print("- Extract bank details using Google Gemini AI")
    print("- Download results as CSV")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
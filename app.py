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
from typing import Dict, Any

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configuration
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Bank Details Extractor</title>
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
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 500px;
            width: 100%;
            text-align: center;
        }
        
        h1 {
            color: #333;
            margin-bottom: 30px;
            font-size: 28px;
            font-weight: 600;
        }
        
        .upload-section {
            margin-bottom: 30px;
        }
        
        .file-input-wrapper {
            position: relative;
            display: inline-block;
            margin-bottom: 20px;
        }
        
        .file-input {
            opacity: 0;
            position: absolute;
            z-index: -1;
        }
        
        .file-input-button {
            background: #667eea;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            border: none;
            font-size: 16px;
            transition: all 0.3s ease;
            display: inline-block;
        }
        
        .file-input-button:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
        }
        
        .file-name {
            margin-top: 10px;
            color: #666;
            font-style: italic;
        }
        
        .button {
            background: #28a745;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            margin: 5px;
            transition: all 0.3s ease;
            min-width: 120px;
        }
        
        .button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .button.download {
            background: #17a2b8;
        }
        
        .button.download:hover {
            background: #138496;
        }
        
        .status {
            margin: 20px 0;
            padding: 15px;
            border-radius: 8px;
            font-weight: 500;
        }
        
        .status.processing {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>PDF Bank Details Extractor</h1>
        
        <div class="upload-section">
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="file-input-wrapper">
                    <input type="file" id="pdfFile" name="pdf_file" accept=".pdf" class="file-input" required>
                    <label for="pdfFile" class="file-input-button">Choose PDF File</label>
                </div>
                <div id="fileName" class="file-name"></div>
                <br>
                <button type="submit" class="button" id="processBtn">
                    Process PDF
                </button>
            </form>
        </div>
        
        <div id="status" class="hidden"></div>
        
        <div id="downloadSection" class="hidden">
            <button id="downloadBtn" class="button download">
                Download CSV
            </button>
        </div>
    </div>

    <script>
        const uploadForm = document.getElementById('uploadForm');
        const pdfFileInput = document.getElementById('pdfFile');
        const fileNameDiv = document.getElementById('fileName');
        const processBtn = document.getElementById('processBtn');
        const statusDiv = document.getElementById('status');
        const downloadSection = document.getElementById('downloadSection');
        const downloadBtn = document.getElementById('downloadBtn');
        
        let currentFilename = '';
        
        // Handle file selection
        pdfFileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                fileNameDiv.textContent = `Selected: ${file.name}`;
                downloadSection.classList.add('hidden');
                statusDiv.classList.add('hidden');
            }
        });
        
        // Handle form submission
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const file = pdfFileInput.files[0];
            if (!file) {
                showStatus('Please select a PDF file first.', 'error');
                return;
            }
            
            if (file.type !== 'application/pdf') {
                showStatus('Please select a valid PDF file.', 'error');
                return;
            }
            
            // Show processing status
            processBtn.disabled = true;
            processBtn.innerHTML = '<span class="loading"></span>Processing...';
            showStatus('Uploading and processing PDF with Gemini AI...', 'processing');
            downloadSection.classList.add('hidden');
            
            // Create form data
            const formData = new FormData();
            formData.append('pdf_file', file);
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentFilename = result.filename;
                    showStatus('PDF processed successfully! Bank details extracted and saved to CSV.', 'success');
                    downloadSection.classList.remove('hidden');
                } else {
                    showStatus(`Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showStatus(`Network error: ${error.message}`, 'error');
            } finally {
                processBtn.disabled = false;
                processBtn.innerHTML = 'Process PDF';
            }
        });
        
        // Handle download
        downloadBtn.addEventListener('click', function() {
            if (currentFilename) {
                window.location.href = `/download/${currentFilename}`;
            }
        });
        
        function showStatus(message, type) {
            statusDiv.textContent = message;
            statusDiv.className = `status ${type}`;
            statusDiv.classList.remove('hidden');
        }
    </script>
</body>
</html>
"""

def encode_pdf_to_base64(file_path):
    """Convert PDF file to base64 for Gemini API"""
    with open(file_path, 'rb') as pdf_file:
        return base64.b64encode(pdf_file.read()).decode('utf-8')


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
    genai.configure(api_key="1111111111111qqqqqqqqqqqqsssssssssffffrrr")
    
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

def save_to_csv(bank_details, filename):
    """Save extracted bank details to CSV file"""
    csv_path = os.path.join(OUTPUT_FOLDER, filename)
    
    # Define CSV headers
    headers = [
        'Account Number', 'Account Name', 'Bank Name', 'Sort Code', 
        'IBAN', 'Swift Code', 'Routing Number', 'BSB Code', 
        'Branch Code', 'Branch Address', 'Account Type', 
        'Currency', 'Balance', 'Other Details'
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        
        if bank_details:
            for detail in bank_details:
                row = [
                    detail.get('account_number', ''),
                    detail.get('account_name', ''),
                    detail.get('bank_name', ''),
                    detail.get('sort_code', ''),
                    detail.get('iban', ''),
                    detail.get('swift_code', ''),
                    detail.get('routing_number', ''),
                    detail.get('bsb_code', ''),
                    detail.get('branch_code', ''),
                    detail.get('branch_address', ''),
                    detail.get('account_type', ''),
                    detail.get('currency', ''),
                    detail.get('balance', ''),
                    detail.get('other_details', '')
                ]
                writer.writerow(row)
        else:
            # Write empty row if no data found
            writer.writerow([''] * len(headers))
    
    return csv_path

@app.route('/')
def index():
    """Main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process_pdf():
    """Process uploaded PDF file"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['pdf_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Please upload a PDF file'})
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, safe_filename)
        file.save(file_path)
        
        try:
            # Convert PDF to base64
            pdf_base64 = encode_pdf_to_base64(file_path)
            
            # Process with Gemini AI
            gemini_response = extract_bank_details_with_gemini(pdf_base64)
            
            # Parse the response
            bank_details = parse_gemini_response(gemini_response)
            
            # Generate CSV filename
            csv_filename = f"bank_details_{timestamp}.csv"
            
            # Save to CSV
            csv_path = save_to_csv(bank_details, csv_filename)
            
            # Clean up uploaded PDF
            os.remove(file_path)
            
            return jsonify({
                'success': True, 
                'filename': csv_filename,
                'records_found': len(bank_details)
            })
            
        except Exception as e:
            # Clean up uploaded file on error
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'success': False, 'error': str(e)})
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

@app.route('/download/<filename>')
def download_csv(filename):
    """Download the generated CSV file"""
    try:
        # Security check: ensure filename doesn't contain path traversal
        secure_name = secure_filename(filename)
        if secure_name != filename:
            return "Invalid filename", 400
        
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            return "File not found", 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    except Exception as e:
        return f"Download error: {str(e)}", 500

if __name__ == '__main__':
    print("Starting PDF Bank Details Extractor...")
    print("Server will be available at: http://localhost:5000")
    print("\nFeatures:")
    print("- Upload PDF files")
    print("- Extract bank details using Google Gemini AI")
    print("- Download results as CSV")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
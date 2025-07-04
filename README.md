# Bank Details Extractor

Extract bank details from PDF documents using Google Gemini AI and FastAPI.

## Features

- Upload PDF files via web interface
- Extract bank details using Google Gemini AI
- Store extracted details in CSV format
- Download combined CSV file
- Session management for tracking processed files

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

- API key is set in `app/core/config.py`
- Default port is 5000

## Usage

1. Start the application:
   ```
   python main.py
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Upload PDF files containing bank details
4. View extracted information and download as CSV

## Project Structure

```
project/
├── app/
│   ├── api/          # API endpoints
│   ├── core/         # Configuration
│   ├── models/       # Pydantic models
│   ├── services/     # Business logic
│   ├── static/       # CSS and JS files
│   ├── templates/    # HTML templates
│   └── utils/        # Utilities
├── uploads/          # Uploaded files
├── output/           # Generated CSV files
├── main.py           # Application entry point
└── requirements.txt  # Dependencies
```

# Bank Details Extractor

Extract bank details from PDF documents using Google Gemini AI and FastAPI.

## Features

- Upload PDF files via web interface
- Extract bank details using Google Gemini AI
- Store extracted details in CSV format
- Download combined CSV file
- Export data as JSON
- Export data to Google Drive
- Session management for tracking processed files
- One-time payment tiers using Yativo payment gateway
- Flexible database backend (SQLite or DynamoDB)

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
4. Copy the example environment file and update it with your settings:
   ```
   cp .env.example .env
   ```
5. Run database migrations:
   ```
   python migrations/add_subscription_and_payment.py
   ```

### Quick Setup with Make

You can use the provided Makefile to quickly set up and run the application:

```bash
# Set up the environment (creates venv and installs dependencies)
make setup-env

# Start the local DynamoDB in Docker
make start-db

# Check if DynamoDB is accessible
make check-db

# Initialize DynamoDB tables
make init-db

# Start the application
make start-app

# Or start both DynamoDB and the application
make start-all
```

## Configuration

### Database Configuration
The application supports two database backends:
- **SQLite** (default): Simple file-based database, perfect for development and small deployments
- **DynamoDB**: AWS's NoSQL database service, ideal for production and scalable deployments

To configure the database backend, set the `DATABASE_TYPE` environment variable in your `.env` file:
```
DATABASE_TYPE=sqlite  # or dynamodb
```

#### Using DynamoDB

##### Option 1: AWS DynamoDB
If using AWS DynamoDB, you'll need to set the following variables:
```
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
DYNAMODB_TABLE_PREFIX=bank_details_
```

##### Option 2: Local DynamoDB with Docker
For local development, you can run DynamoDB locally using Docker:

```bash
# Start local DynamoDB
make start-db

# Initialize tables
make init-db
```

Configure your `.env` file with:
```
DATABASE_TYPE=dynamodb
AWS_ACCESS_KEY_ID=dummy
AWS_SECRET_ACCESS_KEY=dummy
AWS_REGION=us-east-1
DYNAMODB_ENDPOINT_URL=http://localhost:8000
DYNAMODB_TABLE_PREFIX=bank_details_
```

### Google Gemini API
- API key is set in `app/core/config.py`

### Google Drive API
1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Drive API
3. Create OAuth 2.0 credentials (Web application type)
4. Add `http://localhost:5000/drive/callback` as an authorized redirect URI
5. Download the credentials JSON file and save it as `credentials.json` in the project root

### Yativo Payment Gateway
1. Create a Yativo business account at [yativo.com](https://yativo.com/)
2. Obtain API keys from your Yativo dashboard
3. Set environment variables:
   ```
   YATIVO_SECRET_KEY=your_secret_key_here
   YATIVO_BASE_URL=https://api.yativo.com  # or https://sandbox.yativo.com for testing
   ```

### General
- Default port is 5000

## Usage

1. Start the application:
   ```
   python main.py
   ```
   Or with Make:
   ```
   make start-app
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Upload PDF files containing bank details
4. View extracted information and download as CSV, JSON, or export to Google Drive

### Export Options

- **CSV/Excel**: Download structured data as CSV or Excel file
- **JSON**: Get the raw JSON data extracted by Gemini AI
- **Google Drive**: Export data directly to your Google Drive account (requires authorization)

### Payment Tiers

The application offers four subscription tiers:

- **Free**: Limited to 5 document uploads, basic extraction, CSV export
- **Basic ($29)**: Up to 50 document uploads, advanced extraction, CSV/Excel exports
- **Pro ($79)**: Up to 500 document uploads, all export formats, Google Drive integration
- **Enterprise ($199)**: Unlimited documents, custom fields, API access, priority support

Payments are processed securely through Yativo's hosted checkout page, which supports local payment methods in 30+ countries.

## Project Structure

```
project/
├── app/
│   ├── api/          # API endpoints
│   ├── core/         # Configuration
│   ├── db/           # Database models and operations
│   ├── models/       # Pydantic models
│   ├── services/     # Business logic
│   ├── static/       # CSS and JS files
│   ├── templates/    # HTML templates
│   └── utils/        # Utilities
├── migrations/       # Database migration scripts
├── scripts/          # Utility scripts
├── uploads/          # Uploaded files
├── output/           # Generated CSV files
├── user_credentials/ # Google Drive user credentials
├── credentials.json  # Google OAuth credentials
├── docker-compose.yml # Docker Compose for local DynamoDB
├── Makefile          # Make commands for development
├── main.py           # Application entry point
└── requirements.txt  # Dependencies
```

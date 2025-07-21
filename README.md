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
- AWS integration (S3, Secrets Manager, DynamoDB)

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
4. Set required environment variables (see Configuration section)
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

### AWS Setup

The application can use various AWS services for enhanced functionality in production:

```bash
# Check AWS connectivity and permissions
make check-aws

# Create necessary secrets in AWS Secrets Manager
make create-secrets

# Run the application with AWS services
make run-aws
```

## Configuration

The application is configured using environment variables and AWS Secrets Manager. No .env files are used in production.

### AWS Configuration

The application integrates with multiple AWS services:

#### AWS Credentials

Before using AWS services, ensure your AWS credentials are properly configured using one of these methods:
1. Environment variables: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
2. AWS CLI: Run `aws configure`
3. IAM roles (when running on AWS services like EC2, Lambda)

Set the AWS region:
```
AWS_REGION=us-east-1  # Change to your preferred region
```

#### AWS Secrets Manager

AWS Secrets Manager is the primary source for sensitive configuration in production:
```
USE_AWS_SECRETS=true
AWS_SECRETS_NAME=ai-bank-extractor
```

Create secrets using the provided command:
```bash
make create-secrets
```

This creates a secret containing sensitive values like:
- API keys (Gemini API)
- Secret keys for the application
- OAuth credentials (Google)
- Payment gateway credentials (Yativo)

#### S3 Storage

The application can store uploads and outputs in S3:
```
USE_S3_STORAGE=true
S3_BUCKET=ai-bank-extractor
```

Ensure your AWS user/role has proper permissions on the S3 bucket.

### Database Configuration
The application supports two database backends:
- **SQLite** (default): Simple file-based database, perfect for development and small deployments
- **DynamoDB**: AWS's NoSQL database service, ideal for production and scalable deployments

To configure the database backend, set the `DATABASE_TYPE` environment variable:
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
```

##### Option 2: Local DynamoDB with Docker
For local development, you can run DynamoDB locally using Docker:

```bash
# Start local DynamoDB
make start-db

# Initialize tables
make init-db
```

Configure with:
```
DATABASE_TYPE=dynamodb
AWS_ACCESS_KEY_ID=dummy
AWS_SECRET_ACCESS_KEY=dummy
AWS_REGION=us-east-1
DYNAMODB_ENDPOINT_URL=http://localhost:8000
```

### DynamoDB Table Names
```
USERS_TABLE_NAME=users
HEADER_CONFIGS_TABLE_NAME=header-configs
RAW_EXTRACTIONS_TABLE_NAME=raw-extractions
PAYMENTS_TABLE_NAME=payments
USER_CREDENTIALS_TABLE_NAME=user-credentials
```

### DynamoDB Index Names
```
EMAIL_INDEX_NAME=email-index
GOOGLE_ID_INDEX_NAME=google-id-index
USER_ID_INDEX_NAME=user-id-index
YATIVO_DEPOSIT_ID_INDEX_NAME=yativo-deposit-id-index
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

   For AWS integration:
   ```
   make run-aws
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Upload PDF files containing bank details
4. View extracted information and download as CSV, JSON, or export to Google Drive

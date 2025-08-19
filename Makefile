.PHONY: help setup-env start-db stop-db check-db init-db start-app start-all clean test-dynamodb migrate-credentials test-credentials run create-secrets check-aws

# Default target
help:
	@echo "Available commands:"
	@echo "  make setup-env        - Create virtual environment and install dependencies"
	@echo "  make start-db         - Start local DynamoDB container"
	@echo "  make stop-db          - Stop local DynamoDB container"
	@echo "  make check-db         - Check if DynamoDB is accessible"
	@echo "  make init-db          - Initialize DynamoDB tables"
	@echo "  make start-app        - Start the FastAPI application"
	@echo "  make start-all        - Start DynamoDB and the application"
	@echo "  make test-dynamodb    - Run tests for DynamoDB functions"
	@echo "  make test-credentials - Test credentials storage in DynamoDB"
	@echo "  make migrate-credentials - Migrate credentials from files to database"
	@echo "  make run          - Run app with AWS services"
	@echo "  make create-secrets   - Create secrets in AWS Secrets Manager"
	@echo "  make check-aws        - Check AWS connectivity and permissions"
	@echo "  make clean            - Remove virtual environment and Docker volumes"

# AWS Region settings (used across different commands)
AWS_REGION = sa-east-1

# Setup environment
setup-env:
	@echo "Setting up virtual environment..."
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	@echo "Environment setup complete. Use 'source venv/bin/activate' to activate."

# Start DynamoDB
start-db:
	@echo "Starting local DynamoDB..."
	mkdir -p dynamodb-data
	docker-compose up -d dynamodb-local
	@echo "DynamoDB is running at http://localhost:8000"

# Stop DynamoDB
stop-db:
	@echo "Stopping local DynamoDB..."
	docker-compose down

# Check DynamoDB connection
check-db:
	@echo "Checking DynamoDB connection..."
	. venv/bin/activate && python scripts/check_dynamodb.py

# Initialize DynamoDB tables
init-db: start-db
	@echo "Initializing DynamoDB tables..."
	sleep 2  # Wait for DynamoDB to be fully ready
	. venv/bin/activate && python scripts/init_dynamodb.py

# Test DynamoDB functions
test-dynamodb: start-db
	@echo "Testing DynamoDB functions..."
	sleep 2  # Wait for DynamoDB to be fully ready
	@echo "Setting up test environment..."
	. venv/bin/activate && python scripts/init_dynamodb.py
	@echo "Running DynamoDB tests..."
	. venv/bin/activate && python scripts/test_dynamodb.py

# Start the application
start-app:
	@echo "Starting FastAPI application..."
	. venv/bin/activate && python main.py

# Start everything
start-all: start-db
	@echo "Starting all services..."
	sleep 2  # Wait for DynamoDB to be fully ready
	. venv/bin/activate && python main.py

# Clean up
clean:
	@echo "Cleaning up..."
	docker-compose down -v
	rm -rf venv
	rm -rf dynamodb-data
	@echo "Cleanup complete" 

# Migrate credentials
migrate-credentials: start-db
	@echo "Migrating credentials from files to database..."
	sleep 2  # Wait for DynamoDB to be fully ready
	. venv/bin/activate && python scripts/init_dynamodb.py
	@echo "Running credential migration..."
	. venv/bin/activate && python scripts/migrate_credentials.py 

# Test credentials storage
test-credentials: start-db
	@echo "Testing credentials storage in DynamoDB..."
	sleep 2  # Wait for DynamoDB to be fully ready
	@echo "Setting up test environment..."
	. venv/bin/activate && python scripts/init_dynamodb.py
	@echo "Running credentials tests..."
	. venv/bin/activate && python scripts/test_credentials_storage.py 

# Check AWS connectivity and permissions
check-aws:
	@echo "Checking AWS connectivity and permissions..."
	. venv/bin/activate && AWS_REGION=$(AWS_REGION) python scripts/check_aws.py

# Run application with AWS services
run:
	@echo "Running application with AWS services..."
	@echo "Using AWS Secrets Manager for sensitive settings"
	. venv/bin/activate && \
	AWS_REGION=$(AWS_REGION) \
	DATABASE_TYPE=firestore \
	USE_AWS_SECRETS=false \
	AWS_SECRETS_NAME=ai-bank \
	USE_GCP_SECRETS=true \
	GCP_SECRETS_NAME=ai-bank \
	GCP_PROJECT_ID=deploy-bank-app \
	S3_EVENTS_BUCKET=event-bucket-eventss3bucket-kg2tgn26qcmq \
	GCS_BUCKET=event-bucket-weirds \
	DEBUG=true \
	USERS_TABLE_NAME=users \
	HEADER_CONFIGS_TABLE_NAME=header-configs \
	RAW_EXTRACTIONS_TABLE_NAME=raw-extractions \
	PAYMENTS_TABLE_NAME=payments \
	API_KEYS_TABLE_NAME=api-keys \
	USER_CREDENTIALS_TABLE_NAME=user-credentials \
	EMAIL_INDEX_NAME=email-index \
	GOOGLE_ID_INDEX_NAME=google-id-index \
	USER_ID_INDEX_NAME=user-id-index \
	YATIVO_DEPOSIT_ID_INDEX_NAME=yativo-deposit-id-index \
	python main.py

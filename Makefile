.PHONY: help setup-env start-db stop-db check-db init-db start-app start-all clean

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
	@echo "  make clean            - Remove virtual environment and Docker volumes"

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
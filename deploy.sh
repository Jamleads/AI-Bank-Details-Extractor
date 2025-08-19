#!/bin/bash

# AI Bank Details Extractor - AWS Lambda Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
STAGE="dev"
REGION="sa-east-1"
STACK_NAME=""

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -s, --stage STAGE       Deployment stage (dev, staging, prod) [default: dev]"
    echo "  -r, --region REGION     AWS region [default: us-east-1]"
    echo "  -n, --stack-name NAME   CloudFormation stack name [default: ai-bank-extractor-STAGE]"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Deploy to dev stage"
    echo "  $0 -s prod -r us-west-2 # Deploy to prod in us-west-2"
    echo "  $0 --stage staging      # Deploy to staging"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--stage)
            STAGE="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -n|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Set default stack name if not provided
if [ -z "$STACK_NAME" ]; then
    STACK_NAME="ai-bank-extractor-$STAGE"
fi

# Validate stage
if [[ ! "$STAGE" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Invalid stage: $STAGE. Must be dev, staging, or prod."
    exit 1
fi

print_status "Starting deployment..."
print_status "Stage: $STAGE"
print_status "Region: $REGION"
print_status "Stack Name: $STACK_NAME"

# Check if AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS CLI is not configured. Please run 'aws configure' first."
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    print_error "SAM CLI is not installed. Please install it first:"
    print_error "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"
    exit 1
fi

# Create .aws-sam directory if it doesn't exist
mkdir -p .aws-sam

print_status "Building SAM application..."
sam build --use-container

if [ $? -ne 0 ]; then
    print_error "SAM build failed!"
    exit 1
fi

print_status "Deploying to AWS..."

# Deploy with guided prompts for first time, or use saved parameters
if [ -f "samconfig.toml" ]; then
    print_status "Using existing SAM configuration..."
    sam deploy --stack-name "$STACK_NAME" --region "$REGION" --parameter-overrides Stage="$STAGE"
else
    print_warning "First time deployment - using guided mode..."
    sam deploy --guided --stack-name "$STACK_NAME" --region "$REGION" --parameter-overrides Stage="$STAGE"
fi

if [ $? -eq 0 ]; then
    print_status "Deployment successful!"
    
    # Get the API URL from stack outputs
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
        --output text 2>/dev/null)
    
    if [ ! -z "$API_URL" ]; then
        print_status "API URL: $API_URL"
    fi
    
    # Get the S3 bucket name
    S3_BUCKET=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
        --output text 2>/dev/null)
    
    if [ ! -z "$S3_BUCKET" ]; then
        print_status "S3 Bucket: $S3_BUCKET"
    fi
    
    print_status "CloudWatch Logs: /aws/lambda/ai-bank-extractor-$STAGE"
    print_status ""
    print_status "Next steps:"
    print_status "1. Create secrets in AWS Secrets Manager: ai-bank-extractor-$STAGE"
    print_status "2. Add your API keys and credentials to the secret"
    print_status "3. Test your API at: $API_URL"
    
else
    print_error "Deployment failed!"
    exit 1
fi 
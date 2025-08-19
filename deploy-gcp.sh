#!/bin/bash

# AI Bank Details Extractor - GCP Deployment Script
# This script automates the deployment to Google Cloud Platform

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/terraform"

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

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to check if required tools are installed
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    local missing_tools=()
    
    # Check for gcloud
    if ! command -v gcloud &> /dev/null; then
        missing_tools+=("gcloud")
    fi
    
    # Check for terraform
    if ! command -v terraform &> /dev/null; then
        missing_tools+=("terraform")
    fi
    
    # Check for docker
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        echo "Please install the missing tools and try again."
        echo ""
        echo "Installation links:"
        echo "- gcloud: https://cloud.google.com/sdk/docs/install"
        echo "- terraform: https://learn.hashicorp.com/tutorials/terraform/install-cli"
        echo "- docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    print_status "All prerequisites satisfied"
}

# Function to check gcloud authentication
check_gcloud_auth() {
    print_header "Checking Google Cloud Authentication"
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        print_error "No active Google Cloud authentication found"
        echo "Please run: gcloud auth login"
        exit 1
    fi
    
    local active_account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
    print_status "Authenticated as: $active_account"
}

# Function to validate terraform.tfvars
validate_tfvars() {
    print_header "Validating Terraform Variables"
    
    if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
        print_error "terraform.tfvars not found"
        echo "Please copy terraform.tfvars.example to terraform.tfvars and fill in your values:"
        echo "  cp $TERRAFORM_DIR/terraform.tfvars.example $TERRAFORM_DIR/terraform.tfvars"
        exit 1
    fi
    
    print_status "terraform.tfvars found"
    
    # Extract project_id from tfvars
    PROJECT_ID=$(grep '^project_id' "$TERRAFORM_DIR/terraform.tfvars" | cut -d'"' -f2)
    REGION=$(grep '^region' "$TERRAFORM_DIR/terraform.tfvars" | cut -d'"' -f2)
    
    if [ -z "$PROJECT_ID" ]; then
        print_error "project_id not found in terraform.tfvars"
        exit 1
    fi
    
    print_status "Project ID: $PROJECT_ID"
    print_status "Region: ${REGION:-us-central1}"
}

# Function to set gcloud project
set_gcloud_project() {
    print_header "Setting Google Cloud Project"
    
    local current_project=$(gcloud config get-value project 2>/dev/null)
    
    if [ "$current_project" != "$PROJECT_ID" ]; then
        print_status "Setting project to $PROJECT_ID"
        gcloud config set project "$PROJECT_ID"
    else
        print_status "Project already set to $PROJECT_ID"
    fi
}

# Function to enable required APIs
enable_apis() {
    print_header "Enabling Required Google Cloud APIs"
    
    local apis=(
        "cloudbuild.googleapis.com"
        "run.googleapis.com"
        "firestore.googleapis.com"
        "storage.googleapis.com"
        "secretmanager.googleapis.com"
        "artifactregistry.googleapis.com"
        "logging.googleapis.com"
        "monitoring.googleapis.com"
        "iamcredentials.googleapis.com"
    )
    
    print_status "Enabling APIs (this may take a few minutes)..."
    gcloud services enable "${apis[@]}" --quiet
    print_status "APIs enabled successfully"
}

# Function to configure Docker for Artifact Registry
configure_docker() {
    print_header "Configuring Docker for Artifact Registry"
    
    local region=${REGION:-us-central1}
    print_status "Configuring Docker for region: $region"
    
    gcloud auth configure-docker "$region-docker.pkg.dev" --quiet
    print_status "Docker configured successfully"
}

# Function to run Terraform
deploy_infrastructure() {
    print_header "Deploying Infrastructure with Terraform"
    
    cd "$TERRAFORM_DIR"
    
    # Initialize Terraform
    print_status "Initializing Terraform..."
    terraform init
    
    # Plan the deployment
    print_status "Planning deployment..."
    terraform plan -out=tfplan
    
    # Ask for confirmation
    echo ""
    read -p "Do you want to apply these changes? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Deployment cancelled"
        exit 0
    fi
    
    # Apply the plan
    print_status "Applying Terraform plan..."
    terraform apply tfplan
    
    print_status "Infrastructure deployed successfully"
    
    # Get outputs
    CLOUD_RUN_URL=$(terraform output -raw cloud_run_url)
    STORAGE_BUCKET=$(terraform output -raw storage_bucket_name)
    DOCKER_IMAGE_URL=$(terraform output -raw docker_image_url)
    
    cd "$SCRIPT_DIR"
}

# Function to build and deploy the application
deploy_application() {
    print_header "Building and Deploying Application"
    
    # Build Docker image
    print_status "Building Docker image..."
    docker build -t "$DOCKER_IMAGE_URL" .
    
    # Push to Artifact Registry
    print_status "Pushing image to Artifact Registry..."
    docker push "$DOCKER_IMAGE_URL"
    
    # Deploy to Cloud Run
    print_status "Deploying to Cloud Run..."
    gcloud run deploy ai-bank-extractor \
        --image="$DOCKER_IMAGE_URL" \
        --region="${REGION:-us-central1}" \
        --platform=managed \
        --quiet
    
    print_status "Application deployed successfully"
}

# Function to run post-deployment tests
run_tests() {
    print_header "Running Post-Deployment Tests"
    
    # Wait for service to be ready
    print_status "Waiting for service to be ready..."
    sleep 30
    
    # Test health endpoint
    if curl -f "$CLOUD_RUN_URL/health" &> /dev/null; then
        print_status "Health check passed"
    else
        print_warning "Health check failed - service may still be starting"
    fi
    
    # Test main endpoint
    if curl -f "$CLOUD_RUN_URL/" &> /dev/null; then
        print_status "Main endpoint accessible"
    else
        print_warning "Main endpoint not accessible - check logs"
    fi
}

# Function to display deployment summary
show_summary() {
    print_header "Deployment Summary"
    
    echo -e "${GREEN}✅ Infrastructure deployed successfully${NC}"
    echo -e "${GREEN}✅ Application deployed successfully${NC}"
    echo ""
    echo -e "${BLUE}Application URL:${NC} $CLOUD_RUN_URL"
    echo -e "${BLUE}Storage Bucket:${NC} $STORAGE_BUCKET"
    echo -e "${BLUE}Project ID:${NC} $PROJECT_ID"
    echo ""
    echo -e "${YELLOW}Useful Commands:${NC}"
    echo "  View logs:     gcloud logs tail /projects/$PROJECT_ID/logs/run.googleapis.com%2Fstderr --follow"
    echo "  Update secrets: gcloud secrets versions add ai-bank-extractor-secrets --data-file=secrets.json"
    echo "  View metrics:  https://console.cloud.google.com/monitoring?project=$PROJECT_ID"
    echo ""
    echo -e "${GREEN}Deployment completed successfully! 🎉${NC}"
}

# Main execution
main() {
    print_header "AI Bank Details Extractor - GCP Deployment"
    
    # Check command line arguments
    SKIP_INFRA=false
    SKIP_APP=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-infrastructure)
                SKIP_INFRA=true
                shift
                ;;
            --skip-application)
                SKIP_APP=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "OPTIONS:"
                echo "  --skip-infrastructure    Skip Terraform infrastructure deployment"
                echo "  --skip-application      Skip application build and deployment"
                echo "  --help, -h              Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run deployment steps
    check_prerequisites
    check_gcloud_auth
    validate_tfvars
    set_gcloud_project
    enable_apis
    configure_docker
    
    if [ "$SKIP_INFRA" = false ]; then
        deploy_infrastructure
    else
        print_warning "Skipping infrastructure deployment"
        # Still need to get outputs for app deployment
        cd "$TERRAFORM_DIR"
        CLOUD_RUN_URL=$(terraform output -raw cloud_run_url 2>/dev/null || echo "")
        DOCKER_IMAGE_URL=$(terraform output -raw docker_image_url 2>/dev/null || echo "")
        cd "$SCRIPT_DIR"
    fi
    
    if [ "$SKIP_APP" = false ]; then
        deploy_application
    else
        print_warning "Skipping application deployment"
    fi
    
    if [ "$SKIP_INFRA" = false ] && [ "$SKIP_APP" = false ]; then
        run_tests
        show_summary
    fi
}

# Run main function
main "$@"

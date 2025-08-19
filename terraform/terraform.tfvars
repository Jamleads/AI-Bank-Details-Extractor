# Example Terraform variables file
# Copy this to terraform.tfvars and fill in your values

# GCP Project Configuration
project_id = "deploy-bank-app"
region     = "us-central1"
zone       = "us-central1-a"
environment = "prod"

# Firestore Configuration
firestore_location = "us-central1"  # Single region location (matches existing)

# Application Secrets
api_key              = "AIzaSyCrjP4HBMC0RataUj4sThVhVjJZe1xTfXo"
secret_key           = "your-app-secret-key-at-least-32-characters-long"
google_client_id     = "783810249351-qcc3uu1mblul8aoco9h0rvoh91cvqjsk.apps.googleusercontent.com"
google_client_secret = "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"
yativo_secret_key    = "0423145c-4059-4529-b97f-1fb14b2d8e9c"


# Optional: GitHub Integration for CI/CD
github_owner = "your-github-username"
github_repo  = "AI-Bank-Details-Extractor"

# Optional: Custom Domain
custom_domain = "api.yourdomain.com"

# Optional: Cloud Run Configuration
min_instances    = 0
max_instances    = 100
cpu_limit        = "2000m"
memory_limit     = "1Gi"
timeout_seconds  = 60

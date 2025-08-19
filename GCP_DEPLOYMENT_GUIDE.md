# GCP Deployment Guide

This guide covers deploying your AI Bank Details Extractor to Google Cloud Platform using Terraform, replacing your AWS Lambda + DynamoDB + S3 setup with Cloud Run + Firestore + Cloud Storage.

## 🎯 What This Deployment Provides

### AWS → GCP Service Mapping
- **AWS Lambda** → **Cloud Run** (containerized, auto-scaling)
- **DynamoDB** → **Firestore** (NoSQL document database)
- **S3** → **Cloud Storage** (object storage)
- **API Gateway** → **Cloud Run HTTP** (built-in HTTP endpoint)
- **AWS Secrets Manager** → **Google Secret Manager**
- **CloudWatch** → **Cloud Logging & Monitoring**

### Infrastructure Created
- ✅ **Cloud Run service** (your application)
- ✅ **Cloud Storage bucket** (file uploads)
- ✅ **Firestore database** (data storage)
- ✅ **Secret Manager** (application secrets)
- ✅ **Service Account** (IAM permissions)
- ✅ **Artifact Registry** (Docker images)
- ✅ **Monitoring & Alerting** (health checks)
- ✅ **Cloud Build** (CI/CD pipeline)

## 📋 Prerequisites

### 1. Install Required Tools
```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Install Terraform
brew install terraform
# OR
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_darwin_amd64.zip
unzip terraform_1.6.0_darwin_amd64.zip
sudo mv terraform /usr/local/bin/

# Install Docker
brew install docker
# OR download from https://docker.com/get-started
```

### 2. Set Up GCP Project
```bash
# Create a new project (or use existing)
gcloud projects create your-project-id --name="AI Bank Extractor"

# Set as default project
gcloud config set project your-project-id

# Enable billing (required for most services)
# Do this in the console: https://console.cloud.google.com/billing
```

### 3. Authenticate with GCP
```bash
# Authenticate your user account
gcloud auth login

# Set application default credentials
gcloud auth application-default login
```

## 🚀 Deployment Steps

### Step 1: Configure Terraform Variables

1. **Copy the example variables file:**
   ```bash
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   ```

2. **Edit `terraform/terraform.tfvars` with your values:**
   ```hcl
   # Required: GCP Project Configuration
   project_id = "your-gcp-project-id"
   region     = "us-central1"
   environment = "prod"

   # Required: Application Secrets
   api_key              = "your-gemini-api-key"
   secret_key           = "your-32-character-secret-key"
   google_client_id     = "your-google-oauth-client-id"
   google_client_secret = "your-google-oauth-client-secret"
   yativo_secret_key    = "your-yativo-payment-key"

   # Optional: GitHub Integration
   github_owner = "your-github-username"
   github_repo  = "AI-Bank-Details-Extractor"
   ```

### Step 2: Deploy with Automated Script (Recommended)

```bash
# Make script executable (if not already)
chmod +x deploy-gcp.sh

# Run the deployment
./deploy-gcp.sh
```

The script will:
1. ✅ Check prerequisites
2. ✅ Validate configuration
3. ✅ Enable required APIs
4. ✅ Deploy infrastructure with Terraform
5. ✅ Build and deploy your application
6. ✅ Run health checks
7. ✅ Display deployment summary

### Step 3: Manual Deployment (Alternative)

If you prefer manual control:

1. **Deploy Infrastructure:**
   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

2. **Build and Deploy Application:**
   ```bash
   # Get values from Terraform outputs
   PROJECT_ID=$(terraform output -raw project_id)
   REGION=$(terraform output -raw region)
   IMAGE_URL=$(terraform output -raw docker_image_url)

   # Build and push Docker image
   docker build -t $IMAGE_URL .
   docker push $IMAGE_URL

   # Deploy to Cloud Run
   gcloud run deploy ai-bank-extractor \
     --image=$IMAGE_URL \
     --region=$REGION \
     --platform=managed
   ```

## 🔧 Configuration Options

### Environment Variables (automatically set)
```bash
CLOUD=GCP                          # Use GCP services
DATABASE_TYPE=firestore            # Use Firestore database
USE_GCS_STORAGE=true              # Use Cloud Storage
USE_GCP_SECRETS=true              # Use Secret Manager
GCP_PROJECT_ID=your-project-id    # Your GCP project
GCS_BUCKET=your-bucket-name       # Storage bucket
GCP_SECRETS_NAME=your-secret      # Secret Manager secret
```

### Cloud Run Configuration
- **CPU:** 2 vCPUs
- **Memory:** 4GB RAM
- **Timeout:** 15 minutes
- **Concurrency:** 1000 requests per instance
- **Scaling:** 0-100 instances (auto-scaling)

### Storage Configuration
- **Bucket:** Regional storage in your chosen region
- **CORS:** Enabled for web uploads
- **Lifecycle:** Files deleted after 30 days
- **Access:** Service account has admin permissions

## 🔄 CI/CD with Cloud Build

### Automatic Deployments
The Terraform creates a Cloud Build trigger that automatically deploys when you push to your main branch.

### Manual Build Trigger
```bash
# Trigger a build manually
gcloud builds submit --config cloudbuild.yaml .
```

### Connect GitHub Repository
```bash
# Connect your repository for automatic builds
gcloud builds triggers create github \
  --repo-name=AI-Bank-Details-Extractor \
  --repo-owner=your-github-username \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

## 📊 Monitoring and Management

### View Application Logs
```bash
# Stream live logs
gcloud logs tail /projects/your-project-id/logs/run.googleapis.com%2Fstderr --follow

# View in console
https://console.cloud.google.com/logs/query?project=your-project-id
```

### Monitor Performance
```bash
# View metrics in console
https://console.cloud.google.com/monitoring?project=your-project-id

# View Cloud Run service details
https://console.cloud.google.com/run?project=your-project-id
```

### Update Secrets
```bash
# Update secrets in Secret Manager
echo '{"API_KEY":"new-key","SECRET_KEY":"new-secret"}' > secrets.json
gcloud secrets versions add ai-bank-extractor-secrets --data-file=secrets.json
rm secrets.json

# Restart service to pick up new secrets
gcloud run services update ai-bank-extractor --region=us-central1
```

### Scale the Service
```bash
# Update resource limits
gcloud run services update ai-bank-extractor \
  --region=us-central1 \
  --memory=8Gi \
  --cpu=4 \
  --max-instances=200
```

## 🚨 Troubleshooting

### Common Issues

#### 1. "Permission denied" errors
```bash
# Check service account permissions
gcloud projects get-iam-policy your-project-id \
  --filter="bindings.members:ai-bank-extractor-sa@your-project-id.iam.gserviceaccount.com"

# Add missing permissions
gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:ai-bank-extractor-sa@your-project-id.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

#### 2. "Service not found" errors
```bash
# Check if service exists
gcloud run services list --region=us-central1

# Redeploy if missing
gcloud run deploy ai-bank-extractor \
  --image=your-image-url \
  --region=us-central1
```

#### 3. Terraform state issues
```bash
# Refresh Terraform state
cd terraform
terraform refresh

# Import existing resources if needed
terraform import google_cloud_run_service.app_service projects/your-project-id/locations/us-central1/services/ai-bank-extractor
```

#### 4. Build failures
```bash
# Check Cloud Build logs
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")

# Manual build with more verbose output
docker build -t test-image . --progress=plain
```

### Debug Commands

```bash
# Test local Docker build
docker build -t local-test .
docker run -p 8080:8080 -e CLOUD=GCP local-test

# Check service health
curl https://your-cloud-run-url/health

# View detailed service information
gcloud run services describe ai-bank-extractor \
  --region=us-central1 \
  --format="export"
```

## 💰 Cost Optimization

### Expected Costs (approximate)
- **Cloud Run:** $0.40 per 1M requests + $0.0012/vCPU-second
- **Firestore:** $0.06/100K reads, $0.18/100K writes
- **Cloud Storage:** $0.020/GB-month + $0.004/1K requests
- **Secret Manager:** $0.06/10K accesses

### Cost Optimization Tips
```bash
# Set minimum instances to 0 for cost savings
gcloud run services update ai-bank-extractor \
  --region=us-central1 \
  --min-instances=0

# Set up budget alerts
gcloud billing budgets create \
  --billing-account=your-billing-account \
  --display-name="AI Bank Extractor Budget" \
  --budget-amount=100USD
```

## 🔄 Migration from AWS

### Data Migration
1. **Export DynamoDB data** to JSON
2. **Import to Firestore** using the migration scripts
3. **Copy S3 files** to Cloud Storage using `gsutil`

### DNS Migration
1. **Update DNS records** to point to your Cloud Run URL
2. **Set up custom domain** (optional)
3. **Configure SSL certificates** (automatic with Cloud Run)

## 🎉 Deployment Complete!

After successful deployment, you'll have:

- 🌐 **Public URL:** Your Cloud Run service URL
- 💾 **Database:** Firestore with your data
- 📦 **Storage:** Cloud Storage bucket for files
- 🔐 **Secrets:** Secure secret management
- 📊 **Monitoring:** Built-in logging and metrics
- 🔄 **CI/CD:** Automated deployments

Your application is now running on GCP with enterprise-grade scalability, security, and monitoring!

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review Cloud Run logs in the GCP console
3. Verify your Terraform configuration
4. Ensure all required APIs are enabled

---

**Congratulations! You've successfully migrated from AWS to GCP!** 🎊

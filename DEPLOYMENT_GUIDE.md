# AI Bank Details Extractor - GCP Deployment Guide

## 🎯 Overview

This guide covers deploying your AI Bank Details Extractor from AWS to Google Cloud Platform using:
- **Cloud Run** (replaces AWS Lambda)
- **Firestore** (replaces DynamoDB) 
- **Cloud Storage** (replaces S3)
- **Secret Manager** (replaces AWS Secrets Manager)
- **Terraform** (Infrastructure as Code)

**Result:** A fully deployed, auto-scaling application on GCP with enterprise-grade security and monitoring.

---

## 📋 Prerequisites

### 1. Required Tools
```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Install Terraform
brew install terraform
# OR download from: https://releases.hashicorp.com/terraform/

# Install Docker
brew install docker
# OR download from: https://docker.com/get-started
```

### 2. GCP Project Setup
```bash
# Create a new project (or use existing)
gcloud projects create your-project-id --name="AI Bank Extractor"

# Set as default project
gcloud config set project your-project-id

# Enable billing in console: https://console.cloud.google.com/billing
```

### 3. Authentication
```bash
# Authenticate your user account
gcloud auth login

# Set application default credentials (for Terraform)
gcloud auth application-default login

# Configure Docker for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## 🚀 Quick Deployment (5 Steps)

### Step 1: Configure Variables
```bash
# Copy and edit configuration
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars`:
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

# Optional: Resource Limits
timeout_seconds  = 900  # 15 minutes
firestore_location = "us-central1"
```

### Step 2: Deploy Infrastructure
```bash
cd terraform
terraform init
terraform plan
terraform apply -auto-approve
cd ..
```

### Step 3: Build & Push Docker Image
```bash
# Use Google Cloud Build for correct architecture
gcloud builds submit --tag us-central1-docker.pkg.dev/your-project-id/ai-bank-extractor-images/ai-bank-extractor:latest
```

### Step 4: Deploy Application
```bash
gcloud run deploy ai-bank-extractor \
  --image us-central1-docker.pkg.dev/your-project-id/ai-bank-extractor-images/ai-bank-extractor:latest \
  --region us-central1 \
  --service-account ai-bank-extractor-sa@your-project-id.iam.gserviceaccount.com \
  --set-env-vars="CLOUD=GCP,DATABASE_TYPE=firestore,USE_GCS_STORAGE=true,USE_GCP_SECRETS=true,GCP_PROJECT_ID=your-project-id,GCS_BUCKET=your-project-id-ai-bank-extractor-storage,GCP_SECRETS_NAME=ai-bank-extractor-secrets,HOST=0.0.0.0,PRODUCTION=true" \
  --allow-unauthenticated \
  --memory=4Gi \
  --cpu=2 \
  --timeout=900 \
  --max-instances=10
```

### Step 5: Test Deployment
```bash
# Get your service URL
gcloud run services describe ai-bank-extractor --region=us-central1 --format='value(status.url)'

# Test health endpoint
curl https://your-service-url/health
```

**🎉 Done! Your app is live on GCP!**

---

## 🏗️ What Gets Created

### Infrastructure Components
- ✅ **Cloud Run Service** - Your containerized application
- ✅ **Firestore Database** - NoSQL document database
- ✅ **Cloud Storage Bucket** - File storage with CORS & lifecycle
- ✅ **Secret Manager** - Secure secrets storage
- ✅ **Service Account** - IAM with least-privilege permissions
- ✅ **Artifact Registry** - Private Docker image repository
- ✅ **Cloud Scheduler** - Health check monitoring (every 5 minutes)

### Auto-Configured Features
- 🔐 **HTTPS/SSL** - Automatic certificates
- 🌍 **Global Load Balancing** - Built into Cloud Run
- 📈 **Auto-scaling** - 0 to 10 instances based on demand
- 📊 **Logging & Monitoring** - Automatic with Cloud Logging
- 🔄 **Health Checks** - Built-in liveness probes
- 💰 **Cost Optimization** - Pay only for actual usage

---

## 📁 Environment Variables

Your app automatically gets these environment variables:
```bash
CLOUD=GCP                          # Use GCP services
DATABASE_TYPE=firestore            # Use Firestore database  
USE_GCS_STORAGE=true              # Use Cloud Storage
USE_GCP_SECRETS=true              # Use Secret Manager
GCP_PROJECT_ID=your-project-id    # Your GCP project
GCS_BUCKET=your-bucket-name       # Storage bucket name
GCP_SECRETS_NAME=your-secret      # Secret Manager secret name
HOST=0.0.0.0                      # Listen on all interfaces
PRODUCTION=true                   # Production mode
PORT=8080                         # Auto-set by Cloud Run
```

---

## 🔧 Management Commands

### View Application Logs
```bash
# Stream live logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ai-bank-extractor" --follow

# View in console
open "https://console.cloud.google.com/logs/query?project=your-project-id"
```

### Update Application
```bash
# Build new image
gcloud builds submit --tag us-central1-docker.pkg.dev/your-project-id/ai-bank-extractor-images/ai-bank-extractor:latest

# Deploy update (keeps same config)
gcloud run services update ai-bank-extractor --region=us-central1
```

### Update Secrets
```bash
# Create new secret version
echo '{"API_KEY":"new-key","SECRET_KEY":"new-secret"}' > secrets.json
gcloud secrets versions add ai-bank-extractor-secrets --data-file=secrets.json
rm secrets.json

# App will automatically pick up new secrets on restart
```

### Scale Resources
```bash
# Update CPU/Memory limits
gcloud run services update ai-bank-extractor \
  --region=us-central1 \
  --memory=8Gi \
  --cpu=4 \
  --max-instances=20
```

### Monitor Performance
```bash
# View service details
gcloud run services describe ai-bank-extractor --region=us-central1

# Open monitoring dashboard
open "https://console.cloud.google.com/monitoring?project=your-project-id"
```

---

## 🚨 Troubleshooting

### Common Issues & Solutions

#### 1. "Permission denied" errors
```bash
# Check service account permissions
gcloud projects get-iam-policy your-project-id \
  --filter="bindings.members:ai-bank-extractor-sa@your-project-id.iam.gserviceaccount.com"

# Add missing permission
gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:ai-bank-extractor-sa@your-project-id.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

#### 2. "Container failed to start"
```bash
# Check logs for startup errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ai-bank-extractor" --limit=20

# Common fixes:
# - Ensure image is built for linux/amd64 architecture
# - Check that app listens on PORT environment variable
# - Verify all required environment variables are set
```

#### 3. "Image not found"
```bash
# Verify image exists
gcloud container images list --repository=us-central1-docker.pkg.dev/your-project-id/ai-bank-extractor-images

# Rebuild and push
gcloud builds submit --tag us-central1-docker.pkg.dev/your-project-id/ai-bank-extractor-images/ai-bank-extractor:latest
```

#### 4. Terraform state issues
```bash
# Refresh state
cd terraform
terraform refresh

# Import existing resource if needed
terraform import google_cloud_run_service.app_service projects/your-project-id/locations/us-central1/services/ai-bank-extractor
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

# Check resource quotas
gcloud compute project-info describe --format="value(quotas[].limit,quotas[].usage)"
```

---

## 💰 Cost Management

### Expected Monthly Costs (Approximate)
- **Cloud Run**: $0.40 per 1M requests + $0.0012/vCPU-second
- **Firestore**: $0.06/100K reads, $0.18/100K writes  
- **Cloud Storage**: $0.020/GB-month + $0.004/1K requests
- **Secret Manager**: $0.06/10K accesses

**Typical small app**: $10-50/month

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

# Monitor usage
open "https://console.cloud.google.com/billing?project=your-project-id"
```

---

## 🔄 CI/CD Setup (Optional)

### Enable Automatic Deployments
1. **Connect GitHub repository**:
   ```bash
   gcloud builds triggers create github \
     --repo-name=AI-Bank-Details-Extractor \
     --repo-owner=your-github-username \
     --branch-pattern="^main$" \
     --build-config=cloudbuild.yaml
   ```

2. **Push to main branch** → Automatic deployment!

### Manual Build Trigger
```bash
# Trigger build manually
gcloud builds submit --config cloudbuild.yaml .
```

---

## 🔐 Security Best Practices

### Service Account Security
- ✅ **Least Privilege**: Service account has only necessary permissions
- ✅ **No Key Files**: Uses Application Default Credentials
- ✅ **Automatic Rotation**: GCP handles credential rotation

### Network Security
- ✅ **HTTPS Only**: All traffic encrypted
- ✅ **VPC Integration**: Optional VPC connector for private resources
- ✅ **Identity-Based Access**: No exposed ports or IPs

### Secret Management
- ✅ **Encrypted at Rest**: All secrets encrypted in Secret Manager
- ✅ **Access Logging**: All secret access logged
- ✅ **Version Control**: Easy secret rotation

---

## 📊 Monitoring & Alerting

### Built-in Monitoring
- **Request Count/Latency** - Automatic
- **Error Rates** - Automatic  
- **CPU/Memory Usage** - Automatic
- **Instance Count** - Automatic

### Custom Alerts (Optional)
```bash
# Set up error rate alert
gcloud alpha monitoring policies create --policy-from-file=alert-policy.yaml
```

### Health Checks
- **Liveness Probe**: Automatic TCP check on port 8080
- **Custom Health**: Your `/health` endpoint
- **Scheduled Check**: Every 5 minutes via Cloud Scheduler

---

## 🔧 Local Development

### Run Locally with GCP Services
```bash
# Set environment variables
export CLOUD=GCP
export DATABASE_TYPE=firestore
export USE_GCS_STORAGE=true
export USE_GCP_SECRETS=true
export GCP_PROJECT_ID=your-project-id
export GCS_BUCKET=your-bucket-name
export GCP_SECRETS_NAME=your-secret-name
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Run application
python main.py
```

### Test with Local Services
```bash
# Use SQLite + local storage for development
export CLOUD=LOCAL
export DATABASE_TYPE=sqlite
export USE_GCS_STORAGE=false
export USE_GCP_SECRETS=false

python main.py
```

---

## 🆘 Support & Resources

### GCP Documentation
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Firestore Documentation](https://cloud.google.com/firestore/docs)
- [Cloud Storage Documentation](https://cloud.google.com/storage/docs)

### Useful Console Links
- **Cloud Console**: https://console.cloud.google.com
- **Cloud Run**: https://console.cloud.google.com/run
- **Firestore**: https://console.cloud.google.com/firestore  
- **Storage**: https://console.cloud.google.com/storage
- **Secrets**: https://console.cloud.google.com/security/secret-manager
- **Monitoring**: https://console.cloud.google.com/monitoring
- **Logs**: https://console.cloud.google.com/logs

### Emergency Commands
```bash
# Stop all traffic (emergency)
gcloud run services update ai-bank-extractor --region=us-central1 --no-traffic

# Rollback to previous version
gcloud run services update ai-bank-extractor --region=us-central1 --to-revisions=PREVIOUS_REVISION=100

# Scale down to zero
gcloud run services update ai-bank-extractor --region=us-central1 --max-instances=0
```

---

## ✅ Deployment Checklist

Before going live:

### Pre-Deployment
- [ ] Set production secrets in `terraform.tfvars`
- [ ] Review resource quotas and limits
- [ ] Test application locally with GCP services
- [ ] Verify billing is enabled

### Deployment
- [ ] Run `terraform apply` successfully  
- [ ] Build image with Cloud Build
- [ ] Deploy to Cloud Run
- [ ] Test health endpoint
- [ ] Verify application functionality

### Post-Deployment  
- [ ] Set up monitoring alerts
- [ ] Configure budget alerts
- [ ] Test backup/restore procedures
- [ ] Document custom domain setup (if needed)
- [ ] Train team on management commands

---

## 🎉 Congratulations!

You've successfully migrated from AWS to GCP! Your application now benefits from:

- **Better Performance**: Faster cold starts than Lambda
- **Lower Costs**: Pay only for actual usage
- **Easier Management**: Simpler architecture
- **Global Scale**: Built-in global load balancing  
- **Enterprise Security**: GCP's security by default

**Your app is production-ready and enterprise-grade!** 🚀

---

*Last Updated: $(date)*
*Deployment Status: ✅ SUCCESSFUL*

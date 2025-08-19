# **GCP Admin Setup Instructions**
*How to set up the AI Bank Details Extractor deployment requirements*

## **Step 1: Project Setup**

### **Option A: Create New Project**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click **"Select a project"** → **"New Project"**
3. Enter project name: `ai-bank-extractor` (or similar)
4. Select billing account
5. Click **"Create"**

### **Option B: Use Existing Project**
1. Select your existing project from the dropdown
2. Make sure billing is enabled: **Billing** → Check if account is linked

## **Step 2: Grant User Access**
1. Go to **IAM & Admin** → **IAM**
2. Click **"Grant Access"**
3. Enter the user's email address
4. Add role: **"Editor"** or **"Owner"**
5. Click **"Save"**

## **Step 3: Enable Required APIs**
Go to **APIs & Services** → **Library** and enable these APIs:
- Search for **"Cloud Run API"** → Click **"Enable"**
- Search for **"Cloud Storage API"** → Click **"Enable"**
- Search for **"Cloud Firestore API"** → Click **"Enable"**
- Search for **"Secret Manager API"** → Click **"Enable"**
- Search for **"IAM Service Account Credentials API"** → Click **"Enable"**
- Search for **"Cloud Build API"** → Click **"Enable"**
- Search for **"Artifact Registry API"** → Click **"Enable"**

### **Quick Way (Command Line):**
```bash
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable iamcredentials.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

## **Step 4: Create Service Account**

### **Via Console:**
1. Go to **IAM & Admin** → **Service Accounts**
2. Click **"Create Service Account"**
3. **Name:** `ai-bank-extractor-sa`
4. **Description:** `Service account for AI Bank Details Extractor app`
5. Click **"Create and Continue"**

### **Add Required Roles:**
Add these roles one by one:
- `Datastore User`
- `Storage Admin`
- `Secret Manager Secret Accessor`
- `Service Account Token Creator`
- `Logging Writer`

6. Click **"Continue"** → **"Done"**

### **Via Command Line:**
```bash
# Create service account
gcloud iam service-accounts create ai-bank-extractor-sa \
    --description="Service account for AI Bank Details Extractor app" \
    --display-name="AI Bank Extractor SA"

# Add roles
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-bank-extractor-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-bank-extractor-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-bank-extractor-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-bank-extractor-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-bank-extractor-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"
```

## **Step 5: Set Up OAuth Credentials**

1. Go to **APIs & Services** → **Credentials**
2. Click **"Create Credentials"** → **"OAuth 2.0 Client IDs"**
3. **Application type:** Web application
4. **Name:** `AI Bank Extractor OAuth`
5. **Authorized redirect URIs:** 
   - Add: `http://localhost:8000/auth/callback` (for local testing)
   - The Cloud Run URL will be added later after deployment
6. Click **"Create"**
7. **Copy the Client ID and Client Secret** (give these to the developer)

## **Step 6: Verify Setup**

### **Check APIs are enabled:**
```bash
gcloud services list --enabled --filter="name:run.googleapis.com OR name:storage.googleapis.com OR name:firestore.googleapis.com OR name:secretmanager.googleapis.com"
```

### **Check Service Account exists:**
```bash
gcloud iam service-accounts list --filter="email:ai-bank-extractor-sa@*"
```

### **Check User has access:**
1. Go to **IAM & Admin** → **IAM**
2. Look for the user's email with Editor/Owner role

## **Step 7: Give Developer the Following Info**
- **Project ID:** `your-project-id`
- **Service Account Email:** `ai-bank-extractor-sa@your-project-id.iam.gserviceaccount.com`
- **OAuth Client ID:** `123456789-abc...`
- **OAuth Client Secret:** `GOCSPX-xyz...`

---

## **Total Time Required:** 
About **10-15 minutes** if following the console steps, or **5 minutes** using command line.

## **What the Developer Can Do After This:**
Run their automated deployment script and the app will be live!

# AI Bank Details Extractor - GCP Terraform Configuration
# This replaces AWS Lambda + DynamoDB + S3 with Cloud Run + Firestore + Cloud Storage

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Local variables
locals {
  app_name = "ai-bank-extractor"
  labels = {
    app         = local.app_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

# APIs already enabled manually - commenting out to avoid permission issues
# resource "google_project_service" "apis" {
#   for_each = toset([
#     "cloudbuild.googleapis.com",
#     "run.googleapis.com",
#     "firestore.googleapis.com", 
#     "storage.googleapis.com",
#     "secretmanager.googleapis.com",
#     "artifactregistry.googleapis.com",
#     "logging.googleapis.com",
#     "monitoring.googleapis.com",
#     "iamcredentials.googleapis.com"
#   ])
#   
#   service            = each.value
#   disable_on_destroy = false
# }

# Create Artifact Registry for Docker images
resource "google_artifact_registry_repository" "app_repo" {
  # APIs enabled manually
  
  location      = var.region
  repository_id = "${local.app_name}-images"
  description   = "Docker repository for ${local.app_name}"
  format        = "DOCKER"
  
  labels = local.labels
}

# Create Cloud Storage bucket for file uploads
resource "google_storage_bucket" "app_storage" {
  # APIs enabled manually
  
  name     = "${var.project_id}-${local.app_name}-storage"
  location = var.region
  
  # Enable uniform bucket-level access
  uniform_bucket_level_access = true
  
  # CORS configuration for web uploads
  cors {
    origin          = ["*"]
    method          = ["GET", "POST", "PUT", "DELETE", "HEAD"]
    response_header = ["Content-Type", "Access-Control-Allow-Origin"]
    max_age_seconds = 3600
  }
  
  # Lifecycle management - delete files after 30 days
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
  
  # Lifecycle management - delete incomplete multipart uploads after 1 day
  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }
  
  labels = local.labels
}

# Initialize Firestore database
resource "google_firestore_database" "database" {
  # APIs enabled manually
  
  project                     = var.project_id
  name                       = "(default)"
  location_id                = var.firestore_location
  type                       = "FIRESTORE_NATIVE"
  concurrency_mode           = "PESSIMISTIC"
  app_engine_integration_mode = "DISABLED"
  
  # Point-in-time recovery - disabled to match existing
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
  
  # Delete protection - disabled to match existing
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
}

# Create service account for the application
resource "google_service_account" "app_service_account" {
  # APIs enabled manually
  
  account_id   = "${local.app_name}-sa"
  display_name = "AI Bank Extractor Service Account"
  description  = "Service account for ${local.app_name} Cloud Run service"
}

# Grant Firestore permissions to service account
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Grant Cloud Storage permissions to service account
resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Grant Secret Manager permissions to service account
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Grant logging permissions to service account
resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Grant monitoring permissions to service account
resource "google_project_iam_member" "monitoring_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Grant IAM Service Account Token Creator permissions for signing URLs
resource "google_project_iam_member" "service_account_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Create application secrets in Secret Manager
resource "google_secret_manager_secret" "app_secrets" {
  # APIs enabled manually
  
  secret_id = "${local.app_name}-secrets"
  
  labels = local.labels
  
  replication {
    auto {}
  }
}

# Store the secret value (you'll need to update this after deployment)
resource "google_secret_manager_secret_version" "app_secrets_version" {
  secret = google_secret_manager_secret.app_secrets.id
  
  secret_data = jsonencode({
    API_KEY                = var.api_key
    SECRET_KEY            = var.secret_key
    GOOGLE_CLIENT_ID      = var.google_client_id
    GOOGLE_CLIENT_SECRET  = var.google_client_secret
    YATIVO_SECRET_KEY     = var.yativo_secret_key
  })
}

# Cloud Build trigger commented out - requires GitHub repo connection
# Can be enabled later by connecting your GitHub repository
# resource "google_cloudbuild_trigger" "app_trigger" {
#   name        = "${local.app_name}-deploy"
#   description = "Deploy ${local.app_name} to Cloud Run"
#   
#   github {
#     owner = var.github_owner
#     name  = var.github_repo
#     push {
#       branch = "^main$"
#     }
#   }
#   
#   build {
#     step {
#       name = "gcr.io/cloud-builders/docker"
#       args = [
#         "build", "-t",
#         "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/${local.app_name}:$COMMIT_SHA", "."
#       ]
#     }
#     step {
#       name = "gcr.io/cloud-builders/docker"
#       args = ["push", "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/${local.app_name}:$COMMIT_SHA"]
#     }
#     step {
#       name = "gcr.io/google.com/cloudsdktool/cloud-sdk"
#       entrypoint = "gcloud"
#       args = ["run", "deploy", local.app_name, "--image=${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/${local.app_name}:$COMMIT_SHA", "--region=${var.region}"]
#     }
#   }
# }

# Deploy Cloud Run service
resource "google_cloud_run_service" "app_service" {
  depends_on = [
    google_service_account.app_service_account,
    google_storage_bucket.app_storage,
    google_firestore_database.database,
    google_secret_manager_secret_version.app_secrets_version
  ]
  
  name     = local.app_name
  location = var.region
  
  template {
    metadata {
      labels = local.labels
      annotations = {
        "autoscaling.knative.dev/maxScale" = "10"
        "autoscaling.knative.dev/minScale" = "0"
        "run.googleapis.com/cpu-throttling" = "false"
        "run.googleapis.com/execution-environment" = "gen2"
      }
    }
    
    spec {
      service_account_name = google_service_account.app_service_account.email
      
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/${local.app_name}:latest"
        
        ports {
          container_port = 8080
        }
        
        resources {
          limits = {
            cpu    = "2000m"
            memory = "4Gi"
          }
          requests = {
            cpu    = "1000m"
            memory = "2Gi"
          }
        }
        
        env {
          name  = "CLOUD"
          value = "GCP"
        }
        
        env {
          name  = "DATABASE_TYPE"
          value = "firestore"
        }
        
        env {
          name  = "USE_GCS_STORAGE"
          value = "true"
        }
        
        env {
          name  = "USE_GCP_SECRETS"
          value = "true"
        }
        
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        
        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.app_storage.name
        }
        
        env {
          name  = "GCP_SECRETS_NAME"
          value = google_secret_manager_secret.app_secrets.secret_id
        }
        
        env {
          name  = "HOST"
          value = "0.0.0.0"
        }
        
        env {
          name  = "PRODUCTION"
          value = var.environment == "prod" ? "true" : "false"
        }
      }
      
      timeout_seconds = var.timeout_seconds
    }
  }
  
  traffic {
    percent         = 100
    latest_revision = true
  }
  
  lifecycle {
    ignore_changes = [
      template[0].spec[0].containers[0].image,
    ]
  }
}

# Make the Cloud Run service publicly accessible
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_service.app_service.location
  project  = google_cloud_run_service.app_service.project
  service  = google_cloud_run_service.app_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Optional: Custom domain mapping (uncomment if you want to use a custom domain)
# resource "google_cloud_run_domain_mapping" "app_domain" {
#   location = var.region
#   name     = var.custom_domain
#   
#   metadata {
#     namespace = var.project_id
#     labels    = local.labels
#   }
#   
#   spec {
#     route_name = google_cloud_run_service.app_service.name
#   }
# }

# Monitoring alert policy commented out - can be enabled after deployment
# resource "google_monitoring_alert_policy" "high_error_rate" {
#   display_name = "${local.app_name} High Error Rate"
#   combiner     = "OR"
#   
#   conditions {
#     display_name = "Error rate > 5%"
#     condition_threshold {
#       filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${local.app_name}\""
#       duration        = "300s"
#       comparison      = "COMPARISON_GT"
#       threshold_value = 0.05
#       aggregations {
#         alignment_period   = "60s"
#         per_series_aligner = "ALIGN_RATE"
#       }
#     }
#   }
#   notification_channels = []
#   alert_strategy {
#     auto_close = "1800s"
#   }
# }

# Create a Cloud Scheduler job for health checks (optional)
resource "google_cloud_scheduler_job" "health_check" {
  # APIs enabled manually
  
  name             = "${local.app_name}-health-check"
  description      = "Health check for ${local.app_name}"
  schedule         = "*/5 * * * *"  # Every 5 minutes
  time_zone        = "UTC"
  attempt_deadline = "60s"
  
  retry_config {
    retry_count = 3
  }
  
  http_target {
    http_method = "GET"
    uri         = "${google_cloud_run_service.app_service.status[0].url}/health"
    
    oidc_token {
      service_account_email = google_service_account.app_service_account.email
    }
  }
}

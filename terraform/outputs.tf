# Outputs for AI Bank Details Extractor GCP Deployment

output "project_id" {
  description = "The GCP project ID"
  value       = var.project_id
}

output "region" {
  description = "The GCP region"
  value       = var.region
}

output "cloud_run_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_service.app_service.status[0].url
}

output "cloud_run_service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_service.app_service.name
}

output "service_account_email" {
  description = "Email of the service account"
  value       = google_service_account.app_service_account.email
}

output "storage_bucket_name" {
  description = "Name of the Cloud Storage bucket"
  value       = google_storage_bucket.app_storage.name
}

output "storage_bucket_url" {
  description = "URL of the Cloud Storage bucket"
  value       = google_storage_bucket.app_storage.url
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository for Docker images"
  value       = google_artifact_registry_repository.app_repo.name
}

output "docker_image_url" {
  description = "Docker image URL for manual builds"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/ai-bank-extractor:latest"
}

output "firestore_database_name" {
  description = "Name of the Firestore database"
  value       = google_firestore_database.database.name
}

output "secret_manager_secret_name" {
  description = "Name of the Secret Manager secret"
  value       = google_secret_manager_secret.app_secrets.secret_id
}

# Cloud Build trigger output commented out since resource is disabled
# output "cloud_build_trigger_name" {
#   description = "Name of the Cloud Build trigger"
#   value       = google_cloudbuild_trigger.app_trigger.name
# }

# Environment variables for local development
output "environment_variables" {
  description = "Environment variables for local development"
  value = {
    CLOUD                           = "GCP"
    DATABASE_TYPE                   = "firestore"
    USE_GCS_STORAGE                 = "true"
    USE_GCP_SECRETS                 = "true"
    GCP_PROJECT_ID                  = var.project_id
    GCS_BUCKET                      = google_storage_bucket.app_storage.name
    GCP_SECRETS_NAME                = google_secret_manager_secret.app_secrets.secret_id
    GOOGLE_APPLICATION_CREDENTIALS  = "/path/to/your-service-account-key.json"
  }
  sensitive = false
}

# Deployment commands
output "deployment_commands" {
  description = "Commands for manual deployment"
  value = {
    build_image = "docker build -t ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/ai-bank-extractor:latest ."
    push_image  = "docker push ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/ai-bank-extractor:latest"
    deploy_service = "gcloud run deploy ai-bank-extractor --image ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/ai-bank-extractor:latest --region ${var.region} --service-account ${google_service_account.app_service_account.email}"
  }
}

# Useful URLs
output "useful_urls" {
  description = "Useful URLs for management"
  value = {
    cloud_console     = "https://console.cloud.google.com/home/dashboard?project=${var.project_id}"
    cloud_run_console = "https://console.cloud.google.com/run?project=${var.project_id}"
    firestore_console = "https://console.cloud.google.com/firestore?project=${var.project_id}"
    storage_console   = "https://console.cloud.google.com/storage/browser?project=${var.project_id}"
    secrets_console   = "https://console.cloud.google.com/security/secret-manager?project=${var.project_id}"
    monitoring_console = "https://console.cloud.google.com/monitoring?project=${var.project_id}"
    logs_console      = "https://console.cloud.google.com/logs/query?project=${var.project_id}"
  }
}

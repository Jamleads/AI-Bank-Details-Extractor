# Variables for AI Bank Details Extractor GCP Deployment

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The GCP zone for resources"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
  
  validation {
    condition = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "firestore_location" {
  description = "Location for Firestore database"
  type        = string
  default     = "us-central"
  
  validation {
    condition = contains([
      "nam5", "eur3", "asia1",  # Multi-region
      "us-central1", "us-east1", "us-west2", "us-west3", "us-west4",
      "europe-central2", "europe-west1", "europe-west2", "europe-west3",
      "asia-east1", "asia-northeast1", "asia-south1", "asia-southeast1"
    ], var.firestore_location)
    error_message = "Firestore location must be a valid Firestore location."
  }
}

# Application secrets
variable "api_key" {
  description = "Gemini API key"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

variable "google_client_id" {
  description = "Google OAuth client ID"
  type        = string
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth client secret"
  type        = string
  sensitive   = true
}

variable "yativo_secret_key" {
  description = "Yativo payment gateway secret key"
  type        = string
  sensitive   = true
}

# Optional GitHub integration for Cloud Build
variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = ""
}

# Optional custom domain
variable "custom_domain" {
  description = "Custom domain for the application"
  type        = string
  default     = ""
}

# Cloud Run configuration
variable "min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 100
}

variable "cpu_limit" {
  description = "CPU limit for Cloud Run instances"
  type        = string
  default     = "2000m"
}

variable "memory_limit" {
  description = "Memory limit for Cloud Run instances"
  type        = string
  default     = "4Gi"
}

variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 900
}

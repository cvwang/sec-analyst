terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Required GCP APIs
resource "google_project_service" "secretmanager_api" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudrun_api" {
  project            = var.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage_api" {
  project            = var.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "aiplatform_api" {
  project            = var.project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

# Cloud Storage Bucket for SEC Filing Cache & Export Reports
resource "google_storage_bucket" "sec_filings_bucket" {
  name                     = "${var.project_id}-sec-reports"
  project                  = var.project_id
  location                 = var.region
  force_destroy            = false
  public_access_prevention = "enforced"

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.storage_api]
}

# Secret Manager Secret for Gemini API Credentials / App Keys
resource "google_secret_manager_secret" "api_key_secret" {
  secret_id = "sec-edgar-agent-api-key"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.secretmanager_api]
}

resource "google_secret_manager_secret_version" "api_key_secret_version" {
  secret      = google_secret_manager_secret.api_key_secret.id
  secret_data = "PLACEHOLDER_KEY_CHANGE_IN_PROD"
}

# Cloud Run v2 Service for SEC EDGAR Agent Backend
resource "google_cloud_run_v2_service" "agent_service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "REASONING_MODEL"
        value = "gemini-2.5-pro"
      }
      env {
        name  = "TOOL_MODEL"
        value = "gemini-2.5-flash"
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [google_project_service.cloudrun_api]
}

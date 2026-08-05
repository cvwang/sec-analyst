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

resource "google_project_service" "modelarmor_api" {
  project            = var.project_id
  service            = "modelarmor.googleapis.com"
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

# Service Account for SEC EDGAR Agent with Least-Privilege IAM Roles
resource "google_service_account" "sec_analyst_sa" {
  account_id   = "sec-analyst-sa"
  display_name = "SEC EDGAR Natural Language Analyst Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "sa_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sec_analyst_sa.email}"
}

resource "google_project_iam_member" "sa_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.sec_analyst_sa.email}"
}

resource "google_project_iam_member" "sa_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.sec_analyst_sa.email}"
}

resource "google_project_iam_member" "sa_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.sec_analyst_sa.email}"
}


resource "google_project_iam_member" "sa_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.sec_analyst_sa.email}"
}

# Cloud Run v2 Service for SEC EDGAR Agent Backend
resource "google_cloud_run_v2_service" "agent_service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.sec_analyst_sa.email

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
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "REASONING_MODEL"
        value = "gemini-2.5-pro"
      }
      env {
        name  = "TOOL_MODEL"
        value = "gemini-3.5-flash"
      }
      env {
        name  = "MODEL_ARMOR_ENABLED"
        value = "true"
      }
      env {
        name  = "MODEL_ARMOR_TEMPLATE_ID"
        value = "sec-analyst-model-armor-template"
      }
      env {
        name  = "MODEL_ARMOR_LOCATION"
        value = var.region
      }
      env {
        name  = "MODEL_ARMOR_FAIL_OPEN"
        value = "true"
      }
      env {
        name  = "MODEL_ARMOR_UNAVAILABLE_POLICY"
        value = "fail_open"
      }


      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      startup_probe {
        http_get {
          path = "/api/v1/health"
          port = 8080
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/api/v1/health"
          port = 8080
        }
        period_seconds = 15
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [
    google_project_service.cloudrun_api,
    google_project_service.modelarmor_api,
    google_service_account.sec_analyst_sa,
  ]
}

# Allow unauthenticated invocation for backend API (or restrict via IAP)
resource "google_cloud_run_v2_service_iam_member" "noauth" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agent_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# BigQuery Telemetry Sink Dataset & Table
resource "google_bigquery_dataset" "telemetry" {
  dataset_id                 = "sec_edgar_telemetry"
  friendly_name              = "SEC EDGAR Agent Telemetry Dataset"
  description                = "Telemetry sink for LLM token usage, cost tracking, and operational metrics."
  location                   = var.region
  project                    = var.project_id
  delete_contents_on_destroy = false
}

resource "google_bigquery_table" "telemetry_events" {
  dataset_id  = google_bigquery_dataset.telemetry.dataset_id
  table_id    = "telemetry_events"
  project     = var.project_id
  description = "Agent execution telemetry and cost tracking events."

  schema = <<EOF
[
  {"name": "trace_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "session_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "event_type", "type": "STRING", "mode": "REQUIRED"},
  {"name": "model_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "input_tokens", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "output_tokens", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "cached_tokens", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "latency_ms", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "ttft_ms", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "estimated_cost_usd", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "cached_savings_usd", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "tool_calls_count", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "status", "type": "STRING", "mode": "REQUIRED"},
  {"name": "error", "type": "STRING", "mode": "NULLABLE"},
  {"name": "metadata", "type": "JSON", "mode": "NULLABLE"}
]
EOF
}



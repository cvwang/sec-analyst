variable "project_id" {
  type        = string
  description = "GCP Project ID for sandbox deployment"
  default     = "fde-sec-edgar-sandbox-dev"
}

variable "region" {
  type        = string
  description = "GCP Region for cloud resources"
  default     = "us-central1"
}

variable "service_name" {
  type        = string
  description = "Name of the Cloud Run agent service"
  default     = "sec-edgar-analyst"
}


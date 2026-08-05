output "cloud_run_service_url" {
  description = "The HTTP URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.agent_service.uri
}

output "service_account_email" {
  description = "The email address of the Cloud Run agent application service account"
  value       = google_service_account.sec_analyst_sa.email
}

output "sec_reports_bucket" {
  description = "The Google Cloud Storage bucket name for SEC filing reports and exports"
  value       = google_storage_bucket.sec_filings_bucket.name
}

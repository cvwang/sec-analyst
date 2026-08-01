import os
import json
import sys
from google.cloud import storage
from google.cloud import discoveryengine_v1 as discoveryengine
from agent.config import settings

bucket_name = os.getenv("GCS_BUCKET_NAME", "sec-analyst-sec-reports")
print(f"Project ID: {settings.gcp_project_id}")
print(f"Bucket Name: {bucket_name}")

storage_client = storage.Client(project=settings.gcp_project_id)
bucket = storage_client.bucket(bucket_name)

# List all blobs under filings/
blobs = list(bucket.list_blobs(prefix="filings/"))
print(f"Found {len(blobs)} blobs in gs://{bucket_name}/filings/")

jsonl_lines = []
for blob in blobs:
    if not blob.name.endswith(".md") or blob.name.endswith("metadata.jsonl"):
        continue
    
    # Example blob name: filings/TSLA_2023_Item1A_Risk.md or filings/AAPL_2023_10K.md
    basename = os.path.basename(blob.name)
    doc_id = basename.replace(".md", "").replace(" ", "_").replace("-", "_")
    
    # Parse ticker, year, section from filename
    parts = doc_id.split("_")
    ticker = parts[0].upper() if len(parts) > 0 else "SEC"
    
    year = 2023
    for p in parts:
        if p.isdigit() and len(p) == 4:
            year = int(p)
            break
            
    section = "Item 7 - MD&A"
    if "Risk" in doc_id or "Item1A" in doc_id:
        section = "Item 1A - Risk Factors"
        
    doc_entry = {
        "id": doc_id,
        "structData": {
            "ticker": ticker,
            "fiscal_year": year,
            "section": section,
            "company_name": f"{ticker} Corp",
        },
        "content": {
            "mimeType": "text/plain",
            "uri": f"gs://{bucket_name}/{blob.name}",
        }
    }
    jsonl_lines.append(json.dumps(doc_entry))

print(f"Generated {len(jsonl_lines)} metadata manifest entries.")

# Save metadata.jsonl locally and upload to GCS
manifest_content = "\n".join(jsonl_lines)
manifest_blob = bucket.blob("filings/metadata.jsonl")
manifest_blob.upload_from_string(manifest_content, content_type="application/json")
print(f"✅ Successfully uploaded gs://{bucket_name}/filings/metadata.jsonl to GCS!")

# Now trigger Discovery Engine ImportDocuments targeting metadata.jsonl
doc_client = discoveryengine.DocumentServiceClient()
parent = f"projects/{settings.gcp_project_id}/locations/global/collections/default_collection/dataStores/sec-10k-filings-datastore/branches/0"

gcs_source = discoveryengine.GcsSource(
    input_uris=[f"gs://{bucket_name}/filings/metadata.jsonl"],
)

request = discoveryengine.ImportDocumentsRequest(
    parent=parent,
    gcs_source=gcs_source,
    reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.FULL,
)

try:
    print("Launching ImportDocuments operation with metadata.jsonl manifest...")
    operation = doc_client.import_documents(request=request)
    print("🚀 Import operation successfully launched!")
    print("Operation name:", operation.operation.name)
except Exception as e:
    print("Import launch error:", e)

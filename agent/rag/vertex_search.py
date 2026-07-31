"""GCP Vertex AI Search (Discovery Engine) Client for Enterprise SEC 10-K RAG Search.

Connects to Vertex AI Search DataStore 'sec-10k-filings-datastore' on GCP project 'sec-analyst'.
Queries indexed GCS 10-K Markdown filings (gs://sec-analyst-sec-reports/filings/) using enterprise semantic search.
"""

import os
import requests
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agent.config import settings
from agent.observability.logging_config import log_tool_execution


class VertexSearchResult(BaseModel):
    """Result chunk returned by Vertex AI Search DataStore."""

    id: str
    gcs_uri: str
    title: str
    snippet: str
    relevance_score: float = 1.0


class VertexAISearchClient:
    """Client for querying GCP Vertex AI Search DataStores."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        datastore_id: str = "sec-10k-filings-datastore",
        location: str = "global",
    ):
        self.project_id = project_id or settings.gcp_project_id
        self.datastore_id = datastore_id
        self.location = location
        self.endpoint = (
            f"https://discoveryengine.googleapis.com/v1/projects/{self.project_id}/"
            f"locations/{self.location}/collections/default_collection/dataStores/"
            f"{self.datastore_id}/servingConfigs/default_search:search"
        )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Gets Bearer token from GCP ADC."""
        try:
            import google.auth
            import google.auth.transport.requests
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            return {
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
                "x-goog-user-project": self.project_id,
            }
        except Exception:
            return {}

    def search_filings(
        self,
        query: str,
        page_size: int = 5,
    ) -> List[VertexSearchResult]:
        """Executes enterprise vector semantic search against Vertex AI Search DataStore."""
        headers = self._get_auth_headers()
        if not headers:
            return []

        payload = {
            "query": query,
            "pageSize": page_size,
            "queryExpansionSpec": {"condition": "AUTO"},
            "spellCorrectionSpec": {"mode": "AUTO"},
        }

        log_tool_execution(
            tool_name="vertex_ai_search_query",
            stage="intent",
            payload={"datastore_id": self.datastore_id, "query": query},
        )

        try:
            resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                results_raw = data.get("results", [])

                for item in results_raw:
                    doc = item.get("document", {})
                    doc_id = doc.get("id", "")
                    struct_data = doc.get("structData", {})
                    derived_struct = doc.get("derivedStructData", {})

                    snippet = ""
                    snippets_list = derived_struct.get("snippets", [])
                    if snippets_list:
                        snippet = snippets_list[0].get("snippet", "")

                    gcs_uri = struct_data.get("uri") or derived_struct.get("link") or f"gs://sec-analyst-sec-reports/filings/{doc_id}.md"
                    title = struct_data.get("title") or doc_id

                    results.append(
                        VertexSearchResult(
                            id=doc_id,
                            gcs_uri=gcs_uri,
                            title=title,
                            snippet=snippet or str(struct_data)[:500],
                        )
                    )

                log_tool_execution(
                    tool_name="vertex_ai_search_query",
                    stage="outcome",
                    payload={"results_count": len(results)},
                    status="SUCCESS",
                )
                return results
            else:
                log_tool_execution(
                    tool_name="vertex_ai_search_query",
                    stage="outcome",
                    payload={"status_code": resp.status_code, "response": resp.text},
                    status="ERROR",
                )
                return []
        except Exception as e:
            log_tool_execution(
                tool_name="vertex_ai_search_query",
                stage="outcome",
                payload={"error": str(e)},
                status="ERROR",
            )
            return []

"""GCP Model Armor Input/Output Screening Guardrail (SEC-02).

Sanitizes user prompt ingress and model response egress using the official
google-cloud-modelarmor SDK client (`modelarmor_v1.ModelArmorClient`) with typed
requests, smart retry logic for transient errors, explicit fail-closed outage handling,
and gated offline mode configuration.
"""

import os
import re
import time
from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel, Field
import google.auth
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import (
    GoogleAPICallError,
    BadRequest,
    Unauthorized,
    PermissionDenied,
    NotFound,
)
from google.cloud import modelarmor_v1
from agent.config import settings

# Known prompt injection & jailbreak trigger patterns for offline fallback testing
INJECTION_KEYWORDS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"override\s+system\s+prompt",
    r"reveal\s+your\s+system\s+prompt",
    r"you\s+are\s+now\s+in\s+evil\s+mode",
    r"bypass\s+security\s+filters",
    r"jailbreak",
    r"admin_override_token",
]

HARMFUL_RESPONSE_KEYWORDS = [
    r"\[SIMULATED_HARMFUL_OUTPUT\]",
    r"prohibited_content_violation",
]


class ModelArmorResult(BaseModel):
    """Result of Model Armor input/output sanitization screening."""

    is_blocked: bool = False
    matched_filter: Optional[str] = None
    confidence_level: Optional[str] = None
    rejection_message: Optional[str] = None
    filter_details: List[str] = Field(default_factory=list)


class ModelArmorGuard:
    """GCP Model Armor Guardrail service wrapping sanitize_user_prompt and sanitize_model_response SDK calls."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        template_id: Optional[str] = None,
    ):
        self.project_id = project_id or settings.gcp_project_id
        self.location = location or settings.model_armor_location
        self.template_id = template_id or settings.model_armor_template_id
        self.enabled = settings.model_armor_enabled
        self.unavailable_policy = getattr(
            settings, "model_armor_unavailable_policy", "fail_closed"
        ).lower()
        self.offline_mode = getattr(settings, "model_armor_offline_mode", False)

        self.template_path = (
            f"projects/{self.project_id}/locations/{self.location}/templates/{self.template_id}"
        )
        self._client: Optional[modelarmor_v1.ModelArmorClient] = None

    def _get_client(self) -> Optional[modelarmor_v1.ModelArmorClient]:
        """Lazy creation of official google-cloud-modelarmor SDK client."""
        if self._client is not None:
            return self._client
        try:
            client_options = ClientOptions(
                api_endpoint=f"modelarmor.{self.location}.rep.googleapis.com"
            )
            self._client = modelarmor_v1.ModelArmorClient(client_options=client_options)
            return self._client
        except Exception:
            return None

    def _call_with_retry(
        self,
        call_fn: Callable[[], Any],
        max_retries: int = 2,
        initial_backoff_sec: float = 0.5,
    ) -> Any:
        """Executes SDK API call with exponential backoff retries for transient errors only."""
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return call_fn()
            except (BadRequest, Unauthorized, PermissionDenied, NotFound) as non_retryable_err:
                raise non_retryable_err
            except (GoogleAPICallError, Exception) as err:
                last_exception = err
                err_msg = str(err)
                if "API has not been used" in err_msg or "disabled" in err_msg:
                    raise err

                if attempt < max_retries:
                    sleep_dur = initial_backoff_sec * (2**attempt)
                    time.sleep(sleep_dur)
                else:
                    raise last_exception

    def sanitize_user_prompt(self, prompt: str) -> ModelArmorResult:
        """Screen user input prompt before it reaches the LLM (Ingress callback)."""
        if not self.enabled:
            return ModelArmorResult(is_blocked=False)

        # 1. Gated Offline Mode: Only run offline pattern check if explicitly enabled for local dev
        if self.offline_mode:
            return self._check_offline_ingress(prompt)

        # 2. Live Production Path: Go straight to GCP Model Armor SDK Client
        client = self._get_client()
        if client is None:
            err = RuntimeError("ModelArmorClient initialization failed (client is None)")
            return self._handle_outage(stage="ingress", error=err, text=prompt)

        request = modelarmor_v1.SanitizeUserPromptRequest(
            name=self.template_path,
            user_prompt_data=modelarmor_v1.DataItem(text=prompt),
        )

        try:
            response = self._call_with_retry(
                lambda: client.sanitize_user_prompt(request=request, timeout=5.0)
            )
            return self._parse_sdk_response(response, stage="ingress")
        except Exception as err:
            return self._handle_outage(stage="ingress", error=err, text=prompt)

    def sanitize_model_response(self, model_response_text: str) -> ModelArmorResult:
        """Screen model response before it reaches the user (Egress callback)."""
        if not self.enabled:
            return ModelArmorResult(is_blocked=False)

        # 1. Gated Offline Mode: Only run offline pattern check if explicitly enabled for local dev
        if self.offline_mode:
            return self._check_offline_egress(model_response_text)

        # 2. Live Production Path: Go straight to GCP Model Armor SDK Client
        client = self._get_client()
        if client is None:
            err = RuntimeError("ModelArmorClient initialization failed (client is None)")
            return self._handle_outage(stage="egress", error=err, text=model_response_text)

        request = modelarmor_v1.SanitizeModelResponseRequest(
            name=self.template_path,
            model_response_data=modelarmor_v1.DataItem(text=model_response_text),
        )

        try:
            response = self._call_with_retry(
                lambda: client.sanitize_model_response(request=request, timeout=5.0)
            )
            return self._parse_sdk_response(response, stage="egress")
        except Exception as err:
            return self._handle_outage(stage="egress", error=err, text=model_response_text)

    def _handle_outage(
        self, stage: str, error: Exception, text: str = ""
    ) -> ModelArmorResult:
        """Explicit Outage Policy: Decide whether to Fail-Open or Fail-Closed on API failure."""
        if self.unavailable_policy == "fail_open":
            if stage == "ingress":
                return self._check_offline_ingress(text)
            else:
                return self._check_offline_egress(text)

        # Default Hard Security Policy: FAIL CLOSED (Block by default on API outage)
        return ModelArmorResult(
            is_blocked=True,
            matched_filter="MODEL_ARMOR_SERVICE_UNAVAILABLE",
            confidence_level="HIGH",
            rejection_message=(
                f"🛡️ {stage.capitalize()} blocked by security guardrails: "
                "Model Armor service unavailable (Fail-Closed)."
            ),
            filter_details=[f"Outage error: {str(error)}"],
        )

    def _check_offline_ingress(self, prompt: str) -> ModelArmorResult:
        """Pattern matching check for offline testing & local validation."""
        for pattern in INJECTION_KEYWORDS:
            if re.search(pattern, prompt, re.IGNORECASE):
                return ModelArmorResult(
                    is_blocked=True,
                    matched_filter="PROMPT_INJECTION_OR_JAILBREAK",
                    confidence_level="HIGH",
                    rejection_message="🛡️ Request blocked by Model Armor guardrails: Prompt injection or jailbreak attempt detected.",
                    filter_details=["Prompt injection pattern matched"],
                )
        return ModelArmorResult(is_blocked=False)

    def _check_offline_egress(self, text: str) -> ModelArmorResult:
        """Pattern matching check for model response egress offline testing."""
        for pattern in HARMFUL_RESPONSE_KEYWORDS:
            if re.search(pattern, text, re.IGNORECASE):
                return ModelArmorResult(
                    is_blocked=True,
                    matched_filter="HARMFUL_CONTENT",
                    confidence_level="HIGH",
                    rejection_message="🛡️ Model response blocked by Model Armor guardrails: Prohibited content category detected.",
                    filter_details=["Model response safety filter triggered"],
                )
        return ModelArmorResult(is_blocked=False)

    def _parse_sdk_response(self, response: Any, stage: str) -> ModelArmorResult:
        """Parses typed modelarmor_v1 response object using SDK enums."""
        sanitization_result = getattr(response, "sanitization_result", None)
        if not sanitization_result:
            return ModelArmorResult(is_blocked=False)

        match_state = getattr(sanitization_result, "filter_match_state", None)

        if match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND:
            filter_results = getattr(sanitization_result, "filter_results", {})
            matched_categories = []

            items = filter_results.values() if hasattr(filter_results, "values") else filter_results
            for item in items:
                # Inspect typed filter results
                if hasattr(item, "pi_and_jailbreak_filter_result") and item.pi_and_jailbreak_filter_result:
                    if item.pi_and_jailbreak_filter_result.match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND:
                        matched_categories.append("PROMPT_INJECTION_OR_JAILBREAK")
                if hasattr(item, "malicious_uri_filter_result") and item.malicious_uri_filter_result:
                    if item.malicious_uri_filter_result.match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND:
                        matched_categories.append("MALICIOUS_URL")
                if hasattr(item, "rai_filter_result") and item.rai_filter_result:
                    if item.rai_filter_result.match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND:
                        matched_categories.append("HARMFUL_CONTENT")

            cat_str = ", ".join(matched_categories) if matched_categories else "SECURITY_POLICY"
            return ModelArmorResult(
                is_blocked=True,
                matched_filter=cat_str,
                confidence_level="HIGH",
                rejection_message=f"🛡️ {stage.capitalize()} blocked by Model Armor guardrails: {cat_str} detected.",
                filter_details=matched_categories,
            )

        return ModelArmorResult(is_blocked=False)


# Default singleton instance
model_armor_guard = ModelArmorGuard()

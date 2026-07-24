"""Live test script for verifying Vertex AI API connectivity and model invocation in Argolis Sandbox."""

import os
import sys
from google import genai
from agent.config import settings
from agent.orchestrator import RootOrchestrator


def test_vertex_ai_connectivity():
    """Initializes Google GenAI Client targeting Vertex AI in project fde-sec-edgar-sandbox-dev."""
    print("=" * 60)
    print("  Testing Live Vertex AI Connectivity (Argolis Sandbox)")
    print("=" * 60)
    print(f"Project ID : {settings.gcp_project_id}")
    print(f"Region     : {settings.gcp_region}")
    print(f"Reasoning  : {settings.reasoning_model}")
    print(f"Tool Model : {settings.tool_model}")
    print("-" * 60)

    # Check for GEMINI_API_KEY or ADC
    api_key = os.getenv("GEMINI_API_KEY")
    adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")

    client = None
    if api_key:
        print("🔑 GEMINI_API_KEY detected. Testing Gemini Developer API...")
        try:
            client = genai.Client(api_key=api_key)
            print("✅ Google GenAI Client (API Key mode) initialized!")
        except Exception as e:
            print(f"❌ API Key client init failed: {e}")
    else:
        print(f"🔑 Using Application Default Credentials (ADC) at: {adc_path}")
        try:
            client = genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_region,
            )
            print("✅ Google GenAI Client (Vertex AI mode) initialized!")
        except Exception as e:
            print(f"❌ Vertex AI client init failed: {e}")

    if not client:
        print("❌ Could not initialize GenAI Client.")
        return False

    # Test Live Model Call
    test_prompt = "Say hello from SEC EDGAR Financial Analyst Agent and confirm system status in 1 sentence."
    print(f"\nSending test prompt to model '{settings.reasoning_model}'...")
    
    try:
        model_to_use = settings.reasoning_model
        try:
            response = client.models.generate_content(
                model=model_to_use,
                contents=test_prompt,
            )
        except Exception as primary_err:
            if "PERMISSION_DENIED" in str(primary_err) or "403" in str(primary_err):
                print("\n" + "!" * 60)
                print("🔒 IAM PERMISSION DENIED ON VERTEX AI")
                print("!" * 60)
                print(f"Your GCP identity in project '{settings.gcp_project_id}' needs the Vertex AI User role.")
                print("\nTo grant the role in Argolis GCP Sandbox, run:")
                print(f"  gcloud projects add-iam-policy-binding {settings.gcp_project_id} \\")
                print("    --member=\"user:$(gcloud config get-value account)\" \\")
                print("    --role=\"roles/aiplatform.user\"\n")
                print("Or export a GEMINI_API_KEY:")
                print("  export GEMINI_API_KEY=\"your_gemini_api_key\"\n")
                return False
            
            print(f"⚠️ Model '{model_to_use}' error: {primary_err}. Testing 'gemini-2.0-flash'...")
            model_to_use = "gemini-2.0-flash"
            response = client.models.generate_content(
                model=model_to_use,
                contents=test_prompt,
            )

        print("\n--- Live Vertex AI Model Response ---")
        print(response.text.strip())
        print("-------------------------------------")
        print(f"✅ Live Vertex AI connectivity test PASSED (Model: {model_to_use})!")

    except Exception as e:
        print(f"❌ Model generation call failed: {e}")
        return False

    return True


if __name__ == "__main__":
    success = test_vertex_ai_connectivity()
    sys.exit(0 if success else 1)

"""
Resolves the correct API URL and headers for either:
  - Azure OpenAI  (*.openai.azure.com)  → /openai/deployments/{model}/chat/completions?api-version=...
  - Azure AI Foundry Serverless  (*.services.ai.azure.com or *.inference.ai.azure.com)
                                  → /models/chat/completions?api-version=2024-05-01-preview
                                     OR just the base URL if it already ends with /chat/completions

The correct api-version for Azure AI Foundry Serverless is 2024-05-01-preview on the
/models/ path, but the deployment name is NOT part of the URL — it goes in the payload
as `"model": "<deployment-name>"`.

For Azure OpenAI the deployment IS in the URL and the api-version is typically
2024-02-01 or 2024-05-01-preview.
"""

from app.core.config import settings


def _is_azure_openai(endpoint: str) -> bool:
    return 'openai.azure.com' in endpoint


def build_chat_url(endpoint: str) -> str:
    base = endpoint.rstrip('/')

    # Already a full URL (user pasted the complete endpoint)
    if '/chat/completions' in base:
        if '?' not in base:
            base += '?api-version=2024-05-01-preview'
        return base

    if _is_azure_openai(base):
        # Azure OpenAI style: deployment name is in the URL path
        model = settings.AI_MODEL_DEPLOYMENT
        return f'{base}/openai/deployments/{model}/chat/completions?api-version=2024-02-01'

    # Azure AI Foundry / Serverless Inference (services.ai.azure.com, inference.ai.azure.com)
    # Model name goes in the payload body, NOT the URL
    return f'{base}/models/chat/completions?api-version=2024-05-01-preview'


def build_headers(api_key: str) -> dict:
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

from app.core.config import settings
from app.core.exceptions import AIProviderNotConfiguredError
from app.core.logging import get_logger
from app.services.ai.base_provider import BaseAIProvider
logger = get_logger(__name__)
_provider_instance: BaseAIProvider = None
def get_ai_provider() -> BaseAIProvider:
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance
    if not settings.ai_configured:
        raise AIProviderNotConfiguredError()
    from app.services.ai.azure_provider import AzureAIProvider
    _provider_instance = AzureAIProvider()
    logger.info("ai.provider_initialized", provider="azure")
    return _provider_instance
def reset_provider() -> None:
    global _provider_instance
    _provider_instance = None

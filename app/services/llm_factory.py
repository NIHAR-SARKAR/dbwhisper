import logging
from .llm_providers.base import BaseLLMClient
from .llm_providers.openai_provider import OpenAIProvider
from .llm_providers.azure_provider import AzureProvider
from .llm_providers.claude_provider import ClaudeProvider
from .llm_providers.kimi_provider import KimiProvider
from .llm_providers.bedrock_provider import BedrockProvider

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM provider clients based on configuration."""

    _providers = {
        "openai": OpenAIProvider,
        "azure": AzureProvider,
        "claude": ClaudeProvider,
        "kimi": KimiProvider,
        "bedrock": BedrockProvider,
    }

    @staticmethod
    def get_client(provider: str) -> BaseLLMClient:
        """Return the correct provider instance based on config."""
        provider = provider.lower().strip()
        if provider not in LLMFactory._providers:
            raise ValueError(f"Unsupported LLM provider: '{provider}'. Supported: {list(LLMFactory._providers.keys())}")
        logger.info("Using LLM provider: %s", provider)
        return LLMFactory._providers[provider]()

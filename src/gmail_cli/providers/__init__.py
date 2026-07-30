from .base import ModelProvider
from .config import ProviderConfig, load_config, save_config
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .opencode_go_provider import OpenCodeGoProvider

__all__ = [
    "GeminiProvider",
    "ModelProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenCodeGoProvider",
    "ProviderConfig",
    "load_config",
    "save_config",
]


def create_provider(cfg: ProviderConfig) -> ModelProvider:
    if cfg.provider == "openai":
        if not cfg.api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        return OpenAIProvider(api_key=cfg.api_key, model=cfg.openai_model)
    if cfg.provider == "gemini":
        if not cfg.api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        return GeminiProvider(api_key=cfg.api_key, model=cfg.gemini_model)
    if cfg.provider == "ollama":
        return OllamaProvider(base_url=cfg.ollama_url, model=cfg.ollama_model)
    if cfg.provider == "opencode_go":
        if not cfg.api_key:
            raise ValueError("OPENCODE_GO_API_KEY not configured")
        return OpenCodeGoProvider(api_key=cfg.api_key, model=cfg.opencode_go_model)
    raise ValueError(f"Unknown provider: {cfg.provider}")

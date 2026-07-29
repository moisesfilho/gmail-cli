__version__ = "1.0.0-alpha"

from .auth import AuthError, AuthService
from .cli import cli
from .formatter import CliFormatter
from .gmail_client import GmailClient, GmailError
from .models import Draft, Label, Message
from .providers import (
    GeminiProvider,
    ModelProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderConfig,
    create_provider,
    load_config,
    save_config,
)

__all__ = [
    "AuthError",
    "AuthService",
    "CliFormatter",
    "Draft",
    "GeminiProvider",
    "GmailClient",
    "GmailError",
    "Label",
    "Message",
    "ModelProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "ProviderConfig",
    "cli",
    "create_provider",
    "load_config",
    "save_config",
]

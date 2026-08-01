__version__ = "1.3.0-alpha"

from .auth import AuthError, AuthService, CredentialsNotFoundError
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
    "CredentialsNotFoundError",
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

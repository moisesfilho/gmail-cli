__version__ = "1.0.0-alpha"

from .auth import AuthError, AuthService
from .cli import cli
from .formatter import CliFormatter
from .gmail_client import GmailClient, GmailError
from .models import Draft, Label, Message

__all__ = [
    "AuthError",
    "AuthService",
    "CliFormatter",
    "Draft",
    "GmailClient",
    "GmailError",
    "Label",
    "Message",
    "cli",
]

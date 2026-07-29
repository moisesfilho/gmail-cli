import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE = Path.home() / ".gmail_cli_config.json"


@dataclass
class ProviderConfig:
    provider: str = "ollama"
    api_key: str | None = None
    model: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-2.0-flash"


def _load_config_file() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config_file(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def load_config() -> ProviderConfig:
    file_cfg = _load_config_file()
    return ProviderConfig(
        provider=os.environ.get("GMAIL_CLI_PROVIDER") or file_cfg.get("provider") or "ollama",
        api_key=os.environ.get("GMAIL_CLI_API_KEY") or file_cfg.get("api_key"),
        model=os.environ.get("GMAIL_CLI_MODEL") or file_cfg.get("model") or "",
        ollama_url=os.environ.get("GMAIL_CLI_OLLAMA_URL")
        or file_cfg.get("ollama_url")
        or "http://localhost:11434",
        ollama_model=os.environ.get("GMAIL_CLI_OLLAMA_MODEL")
        or file_cfg.get("ollama_model")
        or "llama3.2",
        openai_model=os.environ.get("GMAIL_CLI_OPENAI_MODEL")
        or file_cfg.get("openai_model")
        or "gpt-4o-mini",
        gemini_model=os.environ.get("GMAIL_CLI_GEMINI_MODEL")
        or file_cfg.get("gemini_model")
        or "gemini-2.0-flash",
    )


def save_config(cfg: ProviderConfig) -> None:
    data = {
        "provider": cfg.provider,
        "api_key": cfg.api_key,
        "ollama_url": cfg.ollama_url,
        "ollama_model": cfg.ollama_model,
        "openai_model": cfg.openai_model,
        "gemini_model": cfg.gemini_model,
    }
    _save_config_file({k: v for k, v in data.items() if v})

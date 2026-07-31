import json
import os
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path.home() / ".gmail-cli"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"


@dataclass
class ProviderConfig:
    provider: str = "ollama"
    api_key: str | None = None
    model: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-2.0-flash"
    opencode_go_model: str = "deepseek-v4-flash"
    log_days: int = 120


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
        opencode_go_model=os.environ.get("OPENCODE_GO_MODEL")
        or file_cfg.get("opencode_go_model")
        or "deepseek-v4-flash",
        log_days=int(os.environ.get("GMAIL_CLI_LOG_DAYS") or file_cfg.get("log_days") or 120),
    )


def save_config(cfg: ProviderConfig) -> None:
    data = {
        "provider": cfg.provider,
        "api_key": cfg.api_key,
        "ollama_url": cfg.ollama_url,
        "ollama_model": cfg.ollama_model,
        "openai_model": cfg.openai_model,
        "gemini_model": cfg.gemini_model,
        "opencode_go_model": cfg.opencode_go_model,
        "log_days": cfg.log_days,
    }
    _save_config_file({k: v for k, v in data.items() if v})

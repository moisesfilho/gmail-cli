import requests

from .base import COMMAND_SYSTEM_PROMPT, SYSTEM_PROMPT, ModelProvider


class OllamaProvider(ModelProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate_query(self, natural_language: str) -> str:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": natural_language},
                ],
                "options": {"temperature": 0},
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    def generate_command(self, natural_language: str, commands_help: str) -> str:
        system_prompt = COMMAND_SYSTEM_PROMPT.format(commands_help=commands_help)
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": natural_language},
                ],
                "options": {"temperature": 0},
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

import requests

from .base import (
    COMMAND_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    ModelProvider,
    build_classify_system_prompt,
    build_suggestion_system_prompt,
)


class OllamaProvider(ModelProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        response_language: str = "pt",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.response_language = response_language

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

    def generate_classification_suggestions(
        self, emails_json: str, labels: list[str] | None = None
    ) -> str:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": build_suggestion_system_prompt(self.response_language, labels),
                    },
                    {
                        "role": "user",
                        "content": (
                            emails_json + "\n\nReturn ONLY the JSON array of suggestions. "
                            "Nothing else."
                        ),
                    },
                ],
                "options": {"temperature": 0},
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    def generate_classification_report(
        self, emails_json: str, labels: list[str] | None = None
    ) -> str:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": build_classify_system_prompt(self.response_language, labels),
                    },
                    {
                        "role": "user",
                        "content": (
                            emails_json + "\n\nGenerate ONLY the classification report "
                            "following the specified format. Nothing else."
                        ),
                    },
                ],
                "options": {"temperature": 0},
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

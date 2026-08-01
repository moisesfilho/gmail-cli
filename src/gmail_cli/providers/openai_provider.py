import requests

from .base import (
    COMMAND_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    ModelProvider,
    build_classify_system_prompt,
    build_suggestion_system_prompt,
)


class OpenAIProvider(ModelProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        response_language: str = "pt",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.response_language = response_language
        self.timeout = timeout

    def generate_query(self, natural_language: str) -> str:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": natural_language},
                ],
                "temperature": 0,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def generate_command(self, natural_language: str, commands_help: str) -> str:
        system_prompt = COMMAND_SYSTEM_PROMPT.format(commands_help=commands_help)
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": natural_language},
                ],
                "temperature": 0,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def generate_classification_suggestions(
        self, emails_json: str, labels: list[str] | None = None
    ) -> str:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
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
                "temperature": 0,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def generate_classification_report(
        self, emails_json: str, labels: list[str] | None = None
    ) -> str:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
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
                "temperature": 0,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

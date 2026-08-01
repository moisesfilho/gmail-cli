import requests

from .base import (
    COMMAND_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    ModelProvider,
    build_classify_system_prompt,
    build_suggestion_system_prompt,
)


class GeminiProvider(ModelProvider):
    def __init__(
        self, api_key: str, model: str = "gemini-2.0-flash", response_language: str = "pt"
    ):
        self.api_key = api_key
        self.model = model
        self.response_language = response_language

    def generate_query(self, natural_language: str) -> str:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + natural_language}]}],
                "generationConfig": {"temperature": 0},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def generate_command(self, natural_language: str, commands_help: str) -> str:
        system_prompt = COMMAND_SYSTEM_PROMPT.format(commands_help=commands_help)
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": system_prompt + "\n\n" + natural_language}]}],
                "generationConfig": {"temperature": 0},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def generate_classification_suggestions(self, emails_json: str) -> str:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    build_suggestion_system_prompt(self.response_language)
                                    + "\n\n"
                                    + emails_json
                                    + "\n\nReturn ONLY the JSON array of suggestions. "
                                    "Nothing else."
                                )
                            }
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def generate_classification_report(self, emails_json: str) -> str:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    build_classify_system_prompt(self.response_language)
                                    + "\n\n"
                                    + emails_json
                                    + "\n\nGenerate ONLY the classification report "
                                    "following the specified format. Nothing else."
                                )
                            }
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

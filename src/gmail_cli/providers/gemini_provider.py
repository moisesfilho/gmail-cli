import requests

from .base import CLASSIFY_SYSTEM_PROMPT, COMMAND_SYSTEM_PROMPT, SYSTEM_PROMPT, ModelProvider


class GeminiProvider(ModelProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model

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
                                    CLASSIFY_SYSTEM_PROMPT
                                    + "\n\n"
                                    + emails_json
                                    + "\n\nGere APENAS o relatório de classificação "
                                    "conforme o formato especificado. Nada mais."
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


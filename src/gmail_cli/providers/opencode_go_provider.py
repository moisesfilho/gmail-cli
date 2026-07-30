import requests

from .base import CLASSIFY_SYSTEM_PROMPT, COMMAND_SYSTEM_PROMPT, SYSTEM_PROMPT, ModelProvider

BASE_URL = "https://opencode.ai/zen/go/v1"


class OpenCodeGoProvider(ModelProvider):
    def __init__(self, api_key: str, model: str = "deepseek-v4-flash"):
        self.api_key = api_key
        self.model = model

    def _post(self, system_prompt: str, user_content: str) -> str:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def generate_query(self, natural_language: str) -> str:
        return self._post(SYSTEM_PROMPT, natural_language)

    def generate_command(self, natural_language: str, commands_help: str) -> str:
        system_prompt = COMMAND_SYSTEM_PROMPT.format(commands_help=commands_help)
        return self._post(system_prompt, natural_language)

    def generate_classification_report(self, emails_json: str) -> str:
        user_content = (
            emails_json
            + "\n\nGere APENAS o relatório de classificação "
            "conforme o formato especificado. Nada mais."
        )
        return self._post(CLASSIFY_SYSTEM_PROMPT, user_content)

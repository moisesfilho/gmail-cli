import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from gmail_cli.providers import (
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenCodeGoProvider,
    ProviderConfig,
    create_provider,
    load_config,
    save_config,
)
from gmail_cli.providers.base import (
    COMMAND_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_classify_system_prompt,
    build_suggestion_system_prompt,
)
from gmail_cli.providers.config import DATA_DIR


class TestSystemPrompt:
    def test_contains_keywords(self):
        assert "from:" in SYSTEM_PROMPT
        assert "to:" in SYSTEM_PROMPT
        assert "has:attachment" in SYSTEM_PROMPT
        assert "older_than:" in SYSTEM_PROMPT
        assert "newer_than:" in SYSTEM_PROMPT

    def test_supports_english_input(self):
        assert "'unread' -> is:unread" in SYSTEM_PROMPT
        assert "'today' -> newer_than:1d" in SYSTEM_PROMPT
        assert "Examples (EN):" in SYSTEM_PROMPT
        assert "Examples (EN):" in COMMAND_SYSTEM_PROMPT


class TestBuildClassifySystemPrompt:
    def test_default_uses_portuguese_format(self):
        assert "Resumo Geral" in build_classify_system_prompt()
        assert "General Summary" not in build_classify_system_prompt()

    def test_english_language_uses_english_format(self):
        assert "General Summary" in build_classify_system_prompt("en")
        assert "Resumo Geral" not in build_classify_system_prompt("en")

    def test_instructions_are_in_english(self):
        assert "You are an email classifier." in build_classify_system_prompt()
        assert "You are an email classifier." in build_classify_system_prompt("en")


class TestBuildSuggestionSystemPrompt:
    def test_default_uses_portuguese_format(self):
        prompt = build_suggestion_system_prompt()
        assert "categoria" in prompt
        assert "category" in build_suggestion_system_prompt("en")
        assert '"id"' in prompt

    def test_english_language_uses_english_format(self):
        assert "category" in build_suggestion_system_prompt("en")
        assert "categoria" not in build_suggestion_system_prompt("en")

    def test_instructions_are_in_english(self):
        assert "You are an email classifier." in build_suggestion_system_prompt()
        assert "Return ONLY a JSON array" in build_suggestion_system_prompt("en")

    def test_with_labels_lists_available_labels(self):
        prompt = build_suggestion_system_prompt(labels=["Work", "Personal"])
        assert "AVAILABLE LABELS" in prompt
        assert "Work, Personal" in prompt

    def test_without_labels_has_no_section(self):
        assert "AVAILABLE LABELS" not in build_suggestion_system_prompt()


class TestBuildClassifySystemPromptLabels:
    def test_with_labels_lists_available_labels(self):
        prompt = build_classify_system_prompt(labels=["Work"])
        assert "AVAILABLE LABELS" in prompt
        assert "Work" in prompt

    def test_without_labels_has_no_section(self):
        assert "AVAILABLE LABELS" not in build_classify_system_prompt()


class TestProviderConfig:
    def test_default_values(self):
        cfg = ProviderConfig()
        assert cfg.provider == "ollama"
        assert cfg.api_key is None
        assert cfg.ollama_url == "http://localhost:11434"
        assert cfg.ollama_model == "llama3.2"
        assert cfg.openai_model == "gpt-4o-mini"
        assert cfg.gemini_model == "gemini-2.0-flash"
        assert cfg.opencode_go_model == "deepseek-v4-flash"
        assert cfg.log_days == 120
        assert cfg.response_language == "pt"

    @patch.dict(os.environ, {}, clear=True)
    def test_corrupted_config_file_falls_back(self, tmp_path):
        config_file = DATA_DIR / "config.json"
        backup = None
        if config_file.exists():
            backup = config_file.read_text()
        try:
            config_file.write_text("not valid json")
            cfg = load_config()
            assert cfg.provider == "ollama"
            assert cfg.api_key is None
        finally:
            if backup is not None:
                config_file.write_text(backup)
            elif config_file.exists():
                config_file.unlink()

    @patch.dict(os.environ, {"GMAIL_CLI_PROVIDER": "openai", "GMAIL_CLI_API_KEY": "sk-test"})
    def test_load_from_env(self):
        cfg = load_config()
        assert cfg.provider == "openai"
        assert cfg.api_key == "sk-test"
        assert cfg.response_language == "pt"

    @patch.dict(os.environ, {"GMAIL_CLI_RESPONSE_LANGUAGE": "en"})
    def test_load_response_language_from_env(self):
        cfg = load_config()
        assert cfg.response_language == "en"

    @patch.dict(os.environ, {}, clear=True)
    def test_load_from_file(self, tmp_path):
        config_file = DATA_DIR / "config.json"
        backup = None
        if config_file.exists():
            backup = config_file.read_text()
        try:
            config_file.write_text(
                json.dumps({"provider": "gemini", "api_key": "fake-key", "response_language": "en"})
            )
            cfg = load_config()
            assert cfg.provider == "gemini"
            assert cfg.api_key == "fake-key"
            assert cfg.response_language == "en"
        finally:
            if backup is not None:
                config_file.write_text(backup)
            elif config_file.exists():
                config_file.unlink()


class TestSaveConfig:
    def test_saves_and_loads(self, tmp_path):
        config_file = DATA_DIR / "config.json"
        backup = None
        if config_file.exists():
            backup = config_file.read_text()
        try:
            cfg = ProviderConfig(provider="ollama", ollama_model="llama3.1")
            save_config(cfg)
            loaded = load_config()
            assert loaded.provider == "ollama"
            assert loaded.ollama_model == "llama3.1"
        finally:
            if backup is not None:
                config_file.write_text(backup)
            elif config_file.exists():
                config_file.unlink()


class TestCreateProvider:
    def test_openai_without_key_raises(self):
        cfg = ProviderConfig(provider="openai")
        with pytest.raises(ValueError, match="API_KEY"):
            create_provider(cfg)

    def test_gemini_without_key_raises(self):
        cfg = ProviderConfig(provider="gemini")
        with pytest.raises(ValueError, match="API_KEY"):
            create_provider(cfg)

    def test_unknown_provider_raises(self):
        cfg = ProviderConfig(provider="invalid")
        with pytest.raises(ValueError, match="Unknown"):
            create_provider(cfg)

    def test_ollama_without_key(self):
        cfg = ProviderConfig(provider="ollama")
        provider = create_provider(cfg)
        assert isinstance(provider, OllamaProvider)
        assert provider.base_url == "http://localhost:11434"

    def test_opencode_go_without_key_raises(self):
        cfg = ProviderConfig(provider="opencode_go")
        with pytest.raises(ValueError, match="API_KEY"):
            create_provider(cfg)

    def test_opencode_go_with_key(self):
        cfg = ProviderConfig(provider="opencode_go", api_key="open-code-key")
        provider = create_provider(cfg)
        assert isinstance(provider, OpenCodeGoProvider)
        assert provider.api_key == "open-code-key"
        assert provider.response_language == "pt"

    def test_openai_with_key(self):
        cfg = ProviderConfig(provider="openai", api_key="sk-test")
        provider = create_provider(cfg)
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "sk-test"
        assert provider.response_language == "pt"

    def test_gemini_with_key(self):
        cfg = ProviderConfig(provider="gemini", api_key="gem-key")
        provider = create_provider(cfg)
        assert isinstance(provider, GeminiProvider)
        assert provider.api_key == "gem-key"
        assert provider.response_language == "pt"

    def test_ollama_passes_response_language(self):
        cfg = ProviderConfig(provider="ollama", response_language="en")
        provider = create_provider(cfg)
        assert isinstance(provider, OllamaProvider)
        assert provider.response_language == "en"


class GenerativeResponse:
    def __init__(self, text):
        self.json_data = {"candidates": [{"content": {"parts": [{"text": text}]}}]}

    def json(self):
        return self.json_data

    def raise_for_status(self):
        pass


class ChatResponse:
    def __init__(self, text):
        self.json_data = {"message": {"content": text}}

    def json(self):
        return self.json_data

    def raise_for_status(self):
        pass


class TestOpenAIProvider:
    def test_generate_query(self):
        provider = OpenAIProvider(api_key="sk-test")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": 'from:"john" after:2024/01/01'}}]
            }
            mock_post.return_value = mock_resp

            result = provider.generate_query("emails from John after 2024")
            assert result == 'from:"john" after:2024/01/01'
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["model"] == "gpt-4o-mini"
            assert call_kwargs["headers"]["Authorization"] == "Bearer sk-test"

    def test_generate_query_custom_model(self):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"choices": [{"message": {"content": "test"}}]}
            mock_post.return_value = mock_resp

            provider.generate_query("test")
            assert mock_post.call_args.kwargs["json"]["model"] == "gpt-4"

    def test_http_error(self):
        provider = OpenAIProvider(api_key="sk-test")
        with patch.object(requests, "post") as mock_post:
            mock_post.side_effect = requests.ConnectionError("failed")
            with pytest.raises(requests.ConnectionError):
                provider.generate_query("test")

    def test_generate_command(self):
        provider = OpenAIProvider(api_key="sk-test")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "gmail search --query 'from:john'"}}]
            }
            mock_post.return_value = mock_resp

            result = provider.generate_command("emails from John", "help text")
            assert result == "gmail search --query 'from:john'"
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == COMMAND_SYSTEM_PROMPT.format(
                commands_help="help text"
            )
            assert call_kwargs["json"]["messages"][1]["content"] == "emails from John"

    def test_generate_classification_report(self):
        provider = OpenAIProvider(api_key="sk-test")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Classification Report"}}]
            }
            mock_post.return_value = mock_resp

            result = provider.generate_classification_report("[]")
            assert result == "Classification Report"
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == build_classify_system_prompt()
            assert (
                call_kwargs["json"]["messages"][1]["content"]
                == "[]\n\nGenerate ONLY the classification report "
                "following the specified format. Nothing else."
            )

    def test_generate_classification_suggestions(self):
        provider = OpenAIProvider(api_key="sk-test")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": '[{"id": "1", "category": "Work"}]'}}]
            }
            mock_post.return_value = mock_resp

            result = provider.generate_classification_suggestions("[]")
            assert result == '[{"id": "1", "category": "Work"}]'
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == build_suggestion_system_prompt()
            assert (
                call_kwargs["json"]["messages"][1]["content"]
                == "[]\n\nReturn ONLY the JSON array of suggestions. Nothing else."
            )

    def test_generate_classification_suggestions_with_labels(self):
        provider = OpenAIProvider(api_key="sk-test")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": '[{"id": "1", "category": "Work"}]'}}]
            }
            mock_post.return_value = mock_resp

            provider.generate_classification_suggestions("[]", labels=["Work"])
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == build_suggestion_system_prompt(
                labels=["Work"]
            )


class TestGeminiProvider:
    def test_generate_query(self):
        provider = GeminiProvider(api_key="gem-key")
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = GenerativeResponse('from:"john"')

            result = provider.generate_query("emails from John")
            assert result == 'from:"john"'
            assert "gem-key" in mock_post.call_args.kwargs["params"]["key"]

    def test_http_error(self):
        provider = GeminiProvider(api_key="gem-key")
        with patch.object(requests, "post") as mock_post:
            mock_post.side_effect = requests.ConnectionError("failed")
            with pytest.raises(requests.ConnectionError):
                provider.generate_query("test")

    def test_generate_command(self):
        provider = GeminiProvider(api_key="gem-key")
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = GenerativeResponse("gmail list labels")

            result = provider.generate_command("list labels", "help text")
            assert result == "gmail list labels"
            assert "gem-key" in mock_post.call_args.kwargs["params"]["key"]
            expected_prompt = (
                COMMAND_SYSTEM_PROMPT.format(commands_help="help text") + "\n\n" + "list labels"
            )
            assert (
                mock_post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
                == expected_prompt
            )

    def test_generate_classification_report(self):
        provider = GeminiProvider(api_key="gem-key")
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = GenerativeResponse("Classification Report")

            result = provider.generate_classification_report("[]")
            assert result == "Classification Report"
            assert "gem-key" in mock_post.call_args.kwargs["params"]["key"]
            expected_prompt = (
                build_classify_system_prompt()
                + "\n\n"
                + "[]\n\nGenerate ONLY the classification report "
                "following the specified format. Nothing else."
            )
            assert (
                mock_post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
                == expected_prompt
            )

    def test_generate_classification_suggestions(self):
        provider = GeminiProvider(api_key="gem-key")
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = GenerativeResponse('[{"id": "1", "category": "Work"}]')

            result = provider.generate_classification_suggestions("[]")
            assert result == '[{"id": "1", "category": "Work"}]'
            assert "gem-key" in mock_post.call_args.kwargs["params"]["key"]
            expected_prompt = (
                build_suggestion_system_prompt()
                + "\n\n"
                + "[]\n\nReturn ONLY the JSON array of suggestions. Nothing else."
            )
            assert (
                mock_post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
                == expected_prompt
            )


class TestOllamaProvider:
    def test_generate_query(self):
        provider = OllamaProvider()
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = ChatResponse("is:unread")

            result = provider.generate_query("unread emails")
            assert result == "is:unread"
            assert mock_post.call_args.args[0] == "http://localhost:11434/api/chat"

    def test_custom_url(self):
        provider = OllamaProvider(base_url="http://ollama.local:8080", model="mistral")
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = ChatResponse("test")
            provider.generate_query("test")
            assert mock_post.call_args.args[0] == "http://ollama.local:8080/api/chat"
            assert mock_post.call_args.kwargs["json"]["model"] == "mistral"

    def test_http_error(self):
        provider = OllamaProvider()
        with patch.object(requests, "post") as mock_post:
            mock_post.side_effect = requests.ConnectionError("failed")
            with pytest.raises(requests.ConnectionError):
                provider.generate_query("test")

    def test_generate_command(self):
        provider = OllamaProvider()
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = ChatResponse("gmail search")

            result = provider.generate_command("search emails", "help text")
            assert result == "gmail search"
            assert mock_post.call_args.args[0] == "http://localhost:11434/api/chat"
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == COMMAND_SYSTEM_PROMPT.format(
                commands_help="help text"
            )
            assert call_kwargs["json"]["messages"][1]["content"] == "search emails"

    def test_generate_classification_report(self):
        # Arrange
        provider = OllamaProvider()
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = ChatResponse("Classification Report")

            # Act
            result = provider.generate_classification_report("[]")

            # Assert
            assert result == "Classification Report"
            assert mock_post.call_args.args[0] == "http://localhost:11434/api/chat"
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == build_classify_system_prompt()
            assert (
                call_kwargs["json"]["messages"][1]["content"]
                == "[]\n\nGenerate ONLY the classification report "
                "following the specified format. Nothing else."
            )

    def test_generate_classification_suggestions(self):
        provider = OllamaProvider()
        with patch.object(requests, "post") as mock_post:
            mock_post.return_value = ChatResponse('[{"id": "1", "category": "Work"}]')

            result = provider.generate_classification_suggestions("[]")
            assert result == '[{"id": "1", "category": "Work"}]'
            assert mock_post.call_args.args[0] == "http://localhost:11434/api/chat"
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == build_suggestion_system_prompt()
            assert (
                call_kwargs["json"]["messages"][1]["content"]
                == "[]\n\nReturn ONLY the JSON array of suggestions. Nothing else."
            )


class TestOpenCodeGoProvider:
    def test_generate_query(self):
        provider = OpenCodeGoProvider(api_key="go-key")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": 'from:"john" after:2024/01/01'}}]
            }
            mock_post.return_value = mock_resp

            result = provider.generate_query("emails from John")
            assert result == 'from:"john" after:2024/01/01'
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["model"] == "deepseek-v4-flash"
            assert call_kwargs["json"]["messages"][0]["content"] == SYSTEM_PROMPT
            assert call_kwargs["json"]["messages"][1]["content"] == "emails from John"
            assert call_kwargs["headers"]["Authorization"] == "Bearer go-key"

    def test_generate_command(self):
        provider = OpenCodeGoProvider(api_key="go-key", model="kimi-k3")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"choices": [{"message": {"content": "gmail search"}}]}
            mock_post.return_value = mock_resp

            result = provider.generate_command("search emails", "help text")
            assert result == "gmail search"
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["model"] == "kimi-k3"
            assert call_kwargs["json"]["messages"][0]["content"] == COMMAND_SYSTEM_PROMPT.format(
                commands_help="help text"
            )

    def test_generate_classification_report(self):
        provider = OpenCodeGoProvider(api_key="go-key")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Classification Report"}}]
            }
            mock_post.return_value = mock_resp

            result = provider.generate_classification_report("[]")
            assert result == "Classification Report"
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == build_classify_system_prompt()
            assert (
                call_kwargs["json"]["messages"][1]["content"]
                == "[]\n\nGenerate ONLY the classification report "
                "following the specified format. Nothing else."
            )

    def test_generate_classification_suggestions(self):
        provider = OpenCodeGoProvider(api_key="go-key")
        with patch.object(requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": '[{"id": "1", "category": "Work"}]'}}]
            }
            mock_post.return_value = mock_resp

            result = provider.generate_classification_suggestions("[]")
            assert result == '[{"id": "1", "category": "Work"}]'
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["messages"][0]["content"] == build_suggestion_system_prompt()
            assert (
                call_kwargs["json"]["messages"][1]["content"]
                == "[]\n\nReturn ONLY the JSON array of suggestions. Nothing else."
            )

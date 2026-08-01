import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests as req_lib

from gmail_cli import AuthError, AuthService, CredentialsNotFoundError
from gmail_cli.auth import (
    _OLD_TOKEN_FILE,
    _OLD_TOKEN_FILE_JSON,
    _open_guide_and_wait,
    wait_for_file,
)


class TestAuthService:
    def test_load_credentials_returns_none_when_no_token(self):
        with patch("os.path.exists", return_value=False):
            service = AuthService()
            assert service._load_credentials() is None

    def test_load_credentials_returns_none_on_corrupt_token(self):
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data="")),
            patch("json.load", side_effect=json.JSONDecodeError("bad", "", 0)),
        ):
            service = AuthService()
            assert service._load_credentials() is None

    def test_load_credentials_returns_none_on_credentials_error(self):
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data='{"token": "abc"}')),
            patch("json.load", return_value={"token": "abc"}),
            patch(
                "google.oauth2.credentials.Credentials.from_authorized_user_info",
                side_effect=ValueError("bad creds"),
            ),
        ):
            service = AuthService()
            assert service._load_credentials() is None

    def test_load_credentials_returns_creds(self):
        mock_creds = MagicMock()
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data='{"token": "abc"}')),
            patch("json.load", return_value={"token": "abc"}),
            patch(
                "google.oauth2.credentials.Credentials.from_authorized_user_info",
                return_value=mock_creds,
            ),
        ):
            service = AuthService()
            result = service._load_credentials()
            assert result == mock_creds

    def test_save_credentials(self):
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "abc"}'
        with (
            patch("tempfile.mkstemp", return_value=(1, "/tmp/token.abc.tmp")),
            patch("os.fdopen", mock_open()) as m,
            patch("os.replace") as mock_replace,
            patch("json.loads", return_value={"token": "abc"}),
            patch("json.dump") as mock_dump,
        ):
            service = AuthService()
            service._save_credentials(mock_creds)
            m.assert_called_once_with(1, "w")
            mock_dump.assert_called_once_with({"token": "abc"}, m())
            mock_replace.assert_called_once_with("/tmp/token.abc.tmp", service.TOKEN_FILE)

    def test_save_credentials_cleans_temp_on_error(self):
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "abc"}'
        with (
            patch("tempfile.mkstemp", return_value=(1, "/tmp/token.abc.tmp")),
            patch("os.fdopen", mock_open()),
            patch("os.replace"),
            patch("json.loads", return_value={"token": "abc"}),
            patch("json.dump", side_effect=OSError("boom")),
            patch("os.remove") as mock_remove,
        ):
            service = AuthService()
            with pytest.raises(OSError, match="boom"):
                service._save_credentials(mock_creds)
            mock_remove.assert_called_once_with("/tmp/token.abc.tmp")

    def test_refresh_credentials_expired_with_token(self):
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "token123"

        with patch.object(mock_creds, "refresh") as mock_refresh:
            service = AuthService()
            result = service._refresh_credentials(mock_creds)
            mock_refresh.assert_called_once()
            assert result == mock_creds

    def test_refresh_credentials_not_expired(self):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.refresh_token = "token"
        service = AuthService()
        result = service._refresh_credentials(mock_creds)
        assert result is mock_creds
        mock_creds.refresh.assert_called_once()

    def test_create_from_oauth_flow_raises_without_file(self):
        with (
            patch("os.path.exists", return_value=False),
            patch("gmail_cli.auth._open_guide_and_wait") as mock_guide,
        ):
            mock_guide.side_effect = CredentialsNotFoundError("no file")
            service = AuthService()
            with pytest.raises(CredentialsNotFoundError):
                service._create_from_oauth_flow()

    def test_create_from_oauth_flow_success(self):
        mock_creds = MagicMock()
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        with (
            patch("os.path.exists", return_value=True),
            patch(
                "gmail_cli.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow
            ),
        ):
            service = AuthService()
            result = service._create_from_oauth_flow()
            assert result == mock_creds
            mock_flow.run_local_server.assert_called_once_with(port=0)

    def test_get_service_full_flow(self):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_build = MagicMock()

        with (
            patch.object(AuthService, "_load_credentials", return_value=mock_creds),
            patch.object(AuthService, "_save_credentials") as mock_save,
            patch("gmail_cli.auth.build", return_value=mock_build),
        ):
            service = AuthService()
            result = service.get_service()
            assert result == mock_build
            mock_save.assert_not_called()

    def test_get_service_refreshes_expired_creds(self):
        invalid_creds = MagicMock()
        invalid_creds.valid = False
        valid_creds = MagicMock()
        valid_creds.valid = True

        with (
            patch.object(AuthService, "_load_credentials", return_value=invalid_creds),
            patch.object(
                AuthService, "_refresh_credentials", return_value=valid_creds
            ) as mock_refresh,
            patch.object(AuthService, "_save_credentials"),
            patch("gmail_cli.auth.build") as mock_build,
        ):
            service = AuthService()
            result = service.get_service()
            assert result == mock_build.return_value
            mock_refresh.assert_called_once_with(invalid_creds)

    def test_get_service_creates_new_creds(self):
        with (
            patch.object(AuthService, "_load_credentials", return_value=None),
            pytest.raises(AuthError, match="Authentication token not found"),
        ):
            AuthService().get_service()

    def test_get_service_refresh_fails(self):
        invalid_creds = MagicMock()
        invalid_creds.valid = False

        with (
            patch.object(AuthService, "_load_credentials", return_value=invalid_creds),
            patch.object(AuthService, "_refresh_credentials", return_value=None),
            pytest.raises(AuthError, match="could not be refreshed"),
        ):
            AuthService().get_service()

    def test_login(self):
        mock_creds = MagicMock()
        with (
            patch.object(AuthService, "_create_from_oauth_flow", return_value=mock_creds),
            patch.object(AuthService, "_save_credentials") as mock_save,
        ):
            service = AuthService()
            service.login()
            mock_save.assert_called_once_with(mock_creds)

    def test_revoke_with_token(self):
        mock_creds = MagicMock()
        with (
            patch.object(AuthService, "_load_credentials", return_value=mock_creds),
            patch("os.path.exists", return_value=True),
            patch("os.remove") as mock_remove,
        ):
            service = AuthService()
            service.revoke()
            mock_creds.revoke.assert_called_once()
            mock_remove.assert_called_once_with(service.TOKEN_FILE)

    def test_revoke_without_token(self):
        with patch.object(AuthService, "_load_credentials", return_value=None):
            service = AuthService()
            service.revoke()

    def test_load_credentials_migrates_pickle_token(self):
        mock_creds = MagicMock()
        migrated = {"done": False}

        def exists(path):
            if path == _OLD_TOKEN_FILE:
                return True
            if path == AuthService.TOKEN_FILE:
                return migrated["done"]
            return False

        with (
            patch("os.path.exists", side_effect=exists),
            patch("builtins.open", mock_open(read_data=b"pickle-data")),
            patch("gmail_cli.auth.pickle.load", return_value=mock_creds) as mock_pickle_load,
            patch("json.load", return_value={"token": "abc"}),
            patch("json.loads", return_value={"token": "abc"}),
            patch(
                "google.oauth2.credentials.Credentials.from_authorized_user_info",
                return_value=mock_creds,
            ),
            patch("json.dump", side_effect=lambda *a, **k: migrated.update(done=True)),
            patch("os.remove"),
        ):
            service = AuthService()
            result = service._load_credentials()
            assert result == mock_creds
            mock_pickle_load.assert_called_once()

    def test_migrate_old_token_pickle_removes_old_file(self):
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "abc"}'
        with (
            patch("builtins.open", mock_open()),
            patch("gmail_cli.auth.pickle.load", return_value=mock_creds),
            patch("json.loads", return_value={"token": "abc"}),
            patch("json.dump") as mock_dump,
            patch("os.remove") as mock_remove,
        ):
            AuthService._migrate_old_token("/old/token.pickle", "/new/token.json")
            mock_dump.assert_called_once()
            mock_remove.assert_called_once_with("/old/token.pickle")

    def test_migrate_old_token_json_renames(self):
        with (
            patch("builtins.open", mock_open()),
            patch("os.rename") as mock_rename,
            patch("os.remove") as mock_remove,
        ):
            AuthService._migrate_old_token(_OLD_TOKEN_FILE_JSON, "/new/token.json")
            mock_rename.assert_called_once_with(_OLD_TOKEN_FILE_JSON, "/new/token.json")
            mock_remove.assert_called_once_with(_OLD_TOKEN_FILE_JSON)

    def test_refresh_credentials_without_refresh_token(self):
        mock_creds = MagicMock()
        mock_creds.refresh_token = None
        service = AuthService()
        result = service._refresh_credentials(mock_creds)
        assert result is None
        mock_creds.refresh.assert_not_called()

    def test_refresh_credentials_raises_request_exception(self):
        mock_creds = MagicMock()
        mock_creds.refresh_token = "token"
        mock_creds.refresh.side_effect = req_lib.RequestException("boom")
        service = AuthService()
        result = service._refresh_credentials(mock_creds)
        assert result is None

    def test_refresh_credentials_raises_value_error(self):
        mock_creds = MagicMock()
        mock_creds.refresh_token = "token"
        mock_creds.refresh.side_effect = ValueError("bad")
        service = AuthService()
        result = service._refresh_credentials(mock_creds)
        assert result is None


class TestWaitForFile:
    def test_finds_file(self):
        with patch("os.path.exists", return_value=True):
            wait_for_file("/some/file", timeout=1)

    def test_timeout_raises(self):
        with (
            patch("os.path.exists", return_value=False),
            pytest.raises(CredentialsNotFoundError),
        ):
            wait_for_file("/some/file", timeout=1)


class TestOpenGuide:
    def test_prints_and_waits(self):
        with (
            patch("click.prompt", return_value=""),
            patch("webbrowser.open"),
            patch("gmail_cli.auth.wait_for_file") as mock_wait,
        ):
            _open_guide_and_wait()
            mock_wait.assert_called_once()

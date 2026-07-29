from unittest.mock import MagicMock, mock_open, patch

import pytest

from gmail_cli import AuthError, AuthService


class TestAuthService:
    def test_load_credentials_returns_none_when_no_token(self):
        with patch("os.path.exists", return_value=False):
            service = AuthService()
            assert service._load_credentials() is None

    def test_load_credentials_returns_creds(self):
        mock_creds = MagicMock()
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data='{"token": "abc"}')),
            patch("json.load", return_value={"token": "abc"}),
            patch("google.oauth2.credentials.Credentials.from_authorized_user_info", return_value=mock_creds),
        ):
            service = AuthService()
            result = service._load_credentials()
            assert result == mock_creds

    def test_save_credentials(self):
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "abc"}'
        with (
            patch("builtins.open", mock_open()) as m,
            patch("json.loads", return_value={"token": "abc"}),
            patch("json.dump") as mock_dump,
        ):
            service = AuthService()
            service._save_credentials(mock_creds)
            m.assert_called_once_with(service.TOKEN_FILE, "w")
            mock_dump.assert_called_once_with({"token": "abc"}, m())

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
        service = AuthService()
        result = service._refresh_credentials(mock_creds)
        assert result is None

    def test_create_from_oauth_flow_raises_without_file(self):
        with patch("os.path.exists", return_value=False):
            service = AuthService()
            with pytest.raises(AuthError):
                service._create_from_oauth_flow()

    def test_create_from_oauth_flow_success(self):
        mock_creds = MagicMock()
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        with (
            patch("os.path.exists", return_value=True),
            patch("gmail_cli.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow),
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
            mock_save.assert_called_once_with(mock_creds)

    def test_get_service_refreshes_expired_creds(self):
        invalid_creds = MagicMock()
        invalid_creds.valid = False
        valid_creds = MagicMock()
        valid_creds.valid = True

        with (
            patch.object(AuthService, "_load_credentials", return_value=invalid_creds),
            patch.object(AuthService, "_refresh_credentials", return_value=valid_creds) as mock_refresh,
            patch.object(AuthService, "_save_credentials"),
            patch("gmail_cli.auth.build") as mock_build,
        ):
            service = AuthService()
            result = service.get_service()
            assert result == mock_build.return_value
            mock_refresh.assert_called_once_with(invalid_creds)

    def test_get_service_creates_new_creds(self):
        mock_creds = MagicMock()
        mock_creds.valid = True

        with (
            patch.object(AuthService, "_load_credentials", return_value=None),
            patch.object(AuthService, "_create_from_oauth_flow", return_value=mock_creds) as mock_create,
            patch.object(AuthService, "_save_credentials"),
            patch("gmail_cli.auth.build") as mock_build,
        ):
            service = AuthService()
            result = service.get_service()
            assert result == mock_build.return_value
            mock_create.assert_called_once()

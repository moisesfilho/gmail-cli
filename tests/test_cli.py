import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from gmail_cli import GmailClient, GmailError, ProviderConfig, cli
from gmail_cli.auth import AuthError
from gmail_cli.cli import _create_client
from gmail_cli.models import Draft, Label, Message

_cli_mod = sys.modules["gmail_cli.cli"]
_REAL_REFRESH_BACKGROUND = _cli_mod._refresh_labels_background


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


def invoke(runner, args, mock_client, **kwargs):
    with patch.object(_cli_mod, "_create_client", return_value=mock_client):
        return runner.invoke(cli, args, **kwargs)


class TestEntryPoint:
    def test_main_block(self):
        result = subprocess.run(
            [sys.executable, "-m", "gmail_cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_help_contains_full_command_reference(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Command: gmail config set" in result.output
        assert "Command: gmail prompt" in result.output
        assert "--response-language" in result.output

    def test_create_client(self):
        with patch.object(_cli_mod, "AuthService") as mock_auth:
            mock_service = MagicMock()
            mock_auth.return_value.get_service.return_value = mock_service
            client = _create_client()
            assert isinstance(client, GmailClient)
            assert client._service is mock_service


class TestAuthLogout:
    def test_logout(self, runner):
        with patch.object(_cli_mod, "AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            result = runner.invoke(cli, ["auth", "logout"])
            assert "Token removed" in result.output
            svc_instance.revoke.assert_called_once()


class TestAuthStatus:
    def test_status_authenticated(self, runner):
        with patch.object(_cli_mod, "AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            svc_instance._load_credentials.return_value = MagicMock()
            result = runner.invoke(cli, ["auth", "status"])
            assert "Authenticated" in result.output

    def test_status_credentials_found(self, runner):
        with patch.object(_cli_mod, "AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            svc_instance._load_credentials.return_value = None
            svc_instance.CREDENTIALS_FILE = "/fake/path"
            with patch("os.path.exists", return_value=True):
                result = runner.invoke(cli, ["auth", "status"])
                assert "credentials found" in result.output.lower()

    def test_status_no_credentials(self, runner):
        with patch.object(_cli_mod, "AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            svc_instance._load_credentials.return_value = None
            svc_instance.CREDENTIALS_FILE = "/fake/path"
            with patch("os.path.exists", return_value=False):
                result = runner.invoke(cli, ["auth", "status"])
                assert "No credentials" in result.output


class TestAuthLogin:
    def test_login(self, runner):
        with patch.object(_cli_mod, "AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            result = runner.invoke(cli, ["auth", "login"])
            assert "Authentication complete" in result.output
            svc_instance.login.assert_called_once()


class TestListMessages:
    def test_no_results(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["list", "messages"], mock_client)
        assert result.exit_code == 0
        assert "No messages found." in result.output

    def test_with_results(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="1",
                thread_id="t1",
                from_="a@b.com",
                subject="Hello",
                date="2026-01-01",
                to="me@c.com",
                body="",
                label_ids=[],
            )
        ]
        result = invoke(runner, ["list", "messages"], mock_client)
        assert result.exit_code == 0
        assert "Hello" in result.output

    def test_with_query_and_label(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        invoke(
            runner,
            ["list", "messages", "-q", "from:a", "-l", "INBOX", "--max", "50"],
            mock_client,
        )
        mock_client.list_messages.assert_called_once_with(
            query="from:a", max_results=50, label_ids=["INBOX"]
        )

    def test_auth_error(self, runner, mock_client):
        mock_client.list_messages.side_effect = AuthError("not authorized")
        result = invoke(runner, ["list", "messages"], mock_client)
        assert "not authorized" in result.output

    def test_gmail_error(self, runner, mock_client):
        mock_client.list_messages.side_effect = GmailError("api error")
        result = invoke(runner, ["list", "messages"], mock_client)
        assert "api error" in result.output


class TestListLabels:
    def test_no_results(self, runner, mock_client):
        mock_client.list_labels.return_value = []
        result = invoke(runner, ["list", "labels"], mock_client)
        assert "No labels found." in result.output

    def test_with_results(self, runner, mock_client):
        mock_client.list_labels.return_value = [Label(id="L1", name="Label1")]
        result = invoke(runner, ["list", "labels"], mock_client)
        assert "Label1" in result.output
        assert result.exit_code == 0

    def test_error(self, runner, mock_client):
        mock_client.list_labels.side_effect = GmailError("fail")
        result = invoke(runner, ["list", "labels"], mock_client)
        assert "fail" in result.output
        assert result.exit_code == 0


class TestListDrafts:
    def test_no_results(self, runner, mock_client):
        mock_client.list_drafts.return_value = []
        result = invoke(runner, ["list", "drafts"], mock_client)
        assert "No drafts found." in result.output
        assert result.exit_code == 0

    def test_with_results(self, runner, mock_client):
        mock_client.list_drafts.return_value = [
            Draft(
                id="d1",
                message_id="m1",
                from_="a@b.com",
                subject="Draft",
                date="2026-01-01",
            )
        ]
        result = invoke(runner, ["list", "drafts"], mock_client)
        assert "Draft" in result.output
        assert result.exit_code == 0

    def test_error(self, runner, mock_client):
        mock_client.list_drafts.side_effect = GmailError("fail")
        result = invoke(runner, ["list", "drafts"], mock_client)
        assert "fail" in result.output


class TestShow:
    def test_success(self, runner, mock_client):
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="Subj",
            date="2026-01-01",
            to="me@c.com",
            body="Body",
            label_ids=["INBOX"],
        )
        result = invoke(runner, ["show", "msg1"], mock_client)
        assert result.exit_code == 0
        assert "Subj" in result.output

    def test_error(self, runner, mock_client):
        mock_client.get_message.side_effect = GmailError("not found")
        result = invoke(runner, ["show", "invalid"], mock_client)
        assert "not found" in result.output


class TestSendMessage:
    def test_success(self, runner, mock_client):
        mock_client.send_message.return_value = {"id": "sent1"}
        result = invoke(
            runner,
            ["send", "message", "--to", "b@b.com", "--subject", "Oi", "--body", "Hello"],
            mock_client,
        )
        assert result.exit_code == 0
        assert "Email sent!" in result.output

    def test_with_cc_bcc(self, runner, mock_client):
        mock_client.send_message.return_value = {"id": "s"}
        invoke(
            runner,
            [
                "send",
                "message",
                "--to",
                "b@b.com",
                "--subject",
                "S",
                "--body",
                "B",
                "--cc",
                "c@c.com",
                "--bcc",
                "d@d.com",
            ],
            mock_client,
        )
        mock_client.send_message.assert_called_once_with(
            "b@b.com", "S", "B", cc="c@c.com", bcc="d@d.com", attachments=None
        )

    def test_with_attachment(self, runner, mock_client):
        mock_client.send_message.return_value = {"id": "s"}
        invoke(
            runner,
            [
                "send",
                "message",
                "--to",
                "b@b.com",
                "--subject",
                "S",
                "--body",
                "B",
                "-a",
                "/tmp/f.pdf",
            ],
            mock_client,
        )
        mock_client.send_message.assert_called_once_with(
            "b@b.com", "S", "B", cc=None, bcc=None, attachments=["/tmp/f.pdf"]
        )

    def test_error(self, runner, mock_client):
        mock_client.send_message.side_effect = GmailError("send failed")
        result = invoke(
            runner,
            ["send", "message", "--to", "x@x.com", "--subject", "X", "--body", "X"],
            mock_client,
        )
        assert "send failed" in result.output


class TestLabelCreate:
    def test_success(self, runner, mock_client):
        mock_client.create_label.return_value = {"id": "L1", "name": "Nova"}
        result = invoke(runner, ["label", "create", "Nova"], mock_client)
        assert "Label created: L1 - Nova" in result.output

    def test_error(self, runner, mock_client):
        mock_client.create_label.side_effect = GmailError("fail")
        result = invoke(runner, ["label", "create", "X"], mock_client)
        assert "fail" in result.output


class TestLabelDelete:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["label", "delete", "L1"], mock_client)
        assert "Label L1 deleted." in result.output
        mock_client.delete_label.assert_called_once_with("L1")

    def test_error(self, runner, mock_client):
        mock_client.delete_label.side_effect = GmailError("fail")
        result = invoke(runner, ["label", "delete", "L1"], mock_client)
        assert "fail" in result.output


class TestMarkRead:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["mark", "read", "msg1"], mock_client)
        assert "Message msg1 marked as read." in result.output
        mock_client.modify_message.assert_called_once_with("msg1", remove_labels=["UNREAD"])

    def test_error(self, runner, mock_client):
        mock_client.modify_message.side_effect = GmailError("fail")
        result = invoke(runner, ["mark", "read", "msg1"], mock_client)
        assert "fail" in result.output


class TestMarkUnread:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["mark", "unread", "msg1"], mock_client)
        assert "Message msg1 marked as unread." in result.output
        mock_client.modify_message.assert_called_once_with("msg1", add_labels=["UNREAD"])

    def test_error(self, runner, mock_client):
        mock_client.modify_message.side_effect = GmailError("fail")
        result = invoke(runner, ["mark", "unread", "msg1"], mock_client)
        assert "fail" in result.output


class TestDelete:
    def test_trash(self, runner, mock_client):
        result = invoke(runner, ["delete", "msg1"], mock_client, input="y\n")
        assert result.exit_code == 0
        assert "moved to trash" in result.output
        mock_client.trash_message.assert_called_once_with("msg1")

    def test_permanent(self, runner, mock_client):
        result = invoke(runner, ["delete", "msg1", "--permanent"], mock_client, input="y\n")
        assert result.exit_code == 0
        assert "deleted permanently" in result.output
        mock_client.delete_message.assert_called_once_with("msg1")

    def test_error(self, runner, mock_client):
        mock_client.trash_message.side_effect = GmailError("fail")
        result = invoke(runner, ["delete", "msg1"], mock_client, input="y\n")
        assert "fail" in result.output

    def test_abort(self, runner, mock_client):
        result = invoke(runner, ["delete", "msg1"], mock_client, input="n\n")
        assert result.exit_code != 0


class TestDeleteAll:
    def test_no_results(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["delete-all", "-q", "from:spam"], mock_client, input="y\n")
        assert result.exit_code == 0
        assert "No emails found." in result.output

    def test_trash(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="m1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="",
                to="",
                body="",
                label_ids=[],
            ),
            Message(
                id="m2",
                thread_id="t1",
                from_="a@b.com",
                subject="S2",
                date="",
                to="",
                body="",
                label_ids=[],
            ),
        ]
        result = invoke(runner, ["delete-all", "-q", "from:spam"], mock_client, input="y\n")
        assert "Deleting 2 email(s)" in result.output
        assert mock_client.trash_message.call_count == 2
        mock_client.delete_message.assert_not_called()

    def test_permanent(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="m1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="",
                to="",
                body="",
                label_ids=[],
            ),
        ]
        result = invoke(
            runner, ["delete-all", "--permanent", "-q", "from:spam"], mock_client, input="y\n"
        )
        assert "Deleting 1 email(s)" in result.output
        mock_client.delete_message.assert_called_once_with("m1")
        mock_client.trash_message.assert_not_called()

    def test_error(self, runner, mock_client):
        mock_client.list_messages.side_effect = GmailError("fail")
        result = invoke(runner, ["delete-all", "-q", "from:x"], mock_client, input="y\n")
        assert "fail" in result.output


class TestRestore:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["restore", "msg1"], mock_client)
        assert "restored from trash" in result.output
        mock_client.untrash_message.assert_called_once_with("msg1")

    def test_error(self, runner, mock_client):
        mock_client.untrash_message.side_effect = GmailError("fail")
        result = invoke(runner, ["restore", "msg1"], mock_client)
        assert "fail" in result.output


class TestRestoreAll:
    def test_no_results(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["restore-all", "-q", "in:trash"], mock_client, input="y\n")
        assert "No emails found in trash." in result.output

    def test_success(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="m1",
                thread_id="t1",
                from_="a@b.com",
                subject="R1",
                date="",
                to="",
                body="",
                label_ids=["TRASH"],
            ),
        ]
        result = invoke(runner, ["restore-all", "-q", "in:trash"], mock_client, input="y\n")
        assert "Restoring 1 email(s)" in result.output
        mock_client.untrash_message.assert_called_once_with("m1")

    def test_error(self, runner, mock_client):
        mock_client.list_messages.side_effect = GmailError("fail")
        result = invoke(runner, ["restore-all", "-q", "in:trash"], mock_client, input="y\n")
        assert "fail" in result.output


class TestDraftCreate:
    def test_success(self, runner, mock_client):
        mock_client.create_draft.return_value = {"id": "d1"}
        result = invoke(
            runner,
            ["draft", "create", "--to", "b@b.com", "--subject", "Rasc", "--body", "Corpo"],
            mock_client,
        )
        assert "Draft created!" in result.output
        mock_client.create_draft.assert_called_once_with(
            "b@b.com", "Rasc", "Corpo", cc=None, bcc=None
        )

    def test_with_cc_bcc(self, runner, mock_client):
        mock_client.create_draft.return_value = {"id": "d2"}
        invoke(
            runner,
            [
                "draft",
                "create",
                "--to",
                "b@b.com",
                "--subject",
                "S",
                "--body",
                "B",
                "--cc",
                "c@c.com",
                "--bcc",
                "d@d.com",
            ],
            mock_client,
        )
        mock_client.create_draft.assert_called_once_with(
            "b@b.com", "S", "B", cc="c@c.com", bcc="d@d.com"
        )

    def test_error(self, runner, mock_client):
        mock_client.create_draft.side_effect = GmailError("fail")
        result = invoke(
            runner,
            ["draft", "create", "--to", "a@a.com", "--subject", "X", "--body", "X"],
            mock_client,
        )
        assert "fail" in result.output


class TestDraftSend:
    def test_success(self, runner, mock_client):
        mock_client.send_draft.return_value = {"id": "d1"}
        result = invoke(runner, ["draft", "send", "d1"], mock_client)
        assert "Draft sent!" in result.output
        mock_client.send_draft.assert_called_once_with("d1")

    def test_error(self, runner, mock_client):
        mock_client.send_draft.side_effect = GmailError("fail")
        result = invoke(runner, ["draft", "send", "d1"], mock_client)
        assert "fail" in result.output


class TestDraftDelete:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["draft", "delete", "d1"], mock_client)
        assert "Draft d1 deleted." in result.output
        mock_client.delete_draft.assert_called_once_with("d1")

    def test_error(self, runner, mock_client):
        mock_client.delete_draft.side_effect = GmailError("fail")
        result = invoke(runner, ["draft", "delete", "d1"], mock_client)
        assert "fail" in result.output


class TestAttachments:
    def test_success(self, runner, mock_client):
        mock_client.download_attachments.return_value = ["/tmp/out/doc.pdf"]
        result = invoke(runner, ["attachments", "msg1", "-o", "/tmp/out"], mock_client)
        assert "Attachment saved: /tmp/out/doc.pdf" in result.output
        mock_client.download_attachments.assert_called_once_with("msg1", output_dir="/tmp/out")

    def test_no_files(self, runner, mock_client):
        mock_client.download_attachments.return_value = []
        result = invoke(runner, ["attachments", "msg1"], mock_client)
        assert "No attachments found." in result.output

    def test_error(self, runner, mock_client):
        mock_client.download_attachments.side_effect = GmailError("fail")
        result = invoke(runner, ["attachments", "msg1"], mock_client)
        assert "fail" in result.output


class TestSearch:
    def test_no_results(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["search", "-q", "from:a"], mock_client)
        assert "No emails found." in result.output

    def test_with_results(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="1",
                thread_id="t1",
                from_="a@b.com",
                subject="Found",
                date="2026-01-01",
                to="me@c.com",
                body="",
                label_ids=[],
            )
        ]
        result = invoke(runner, ["search", "-q", "from:a"], mock_client)
        assert "Found" in result.output

    def test_error(self, runner, mock_client):
        mock_client.list_messages.side_effect = GmailError("fail")
        result = invoke(runner, ["search", "-q", "from:a"], mock_client)
        assert "fail" in result.output


class TestPrompt:
    def test_no_provider_shows_error(self, runner, mock_client):
        with patch.object(_cli_mod, "load_config") as mock_load:
            mock_load.return_value = ProviderConfig(provider="openai")
            with patch.object(_cli_mod, "create_provider") as mock_create:
                mock_create.side_effect = ValueError("API_KEY not configured")
                result = runner.invoke(cli, ["prompt", "test"])
                assert "API_KEY" in result.output

    def test_displays_generated_command(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'from:john'"
        with patch.object(_cli_mod, "load_config") as mock_load:
            mock_load.return_value = ProviderConfig(provider="ollama")
            with patch.object(_cli_mod, "create_provider", return_value=mock_provider):
                result = runner.invoke(cli, ["prompt", "emails", "from", "john"], input="n\n")
                assert "gmail search --query 'from:john'" in result.output
                assert "Do you want to run the suggested command?" in result.output
                mock_provider.generate_command.assert_called_once()
                args, _ = mock_provider.generate_command.call_args
                assert args[0] == "emails from john"
                assert "Command: gmail search" in args[1]
                assert "Command: gmail prompt" not in args[1]

    def test_prompt_declines_execution(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'is:unread'"
        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "unread", "emails"], input="n\n")
            assert "Do you want to run the suggested command?" in result.output
            mock_client.list_messages.assert_not_called()

    def test_prompt_accepts_execution_by_confirming(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'is:unread'"
        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            mock_client.list_messages.return_value = [
                Message(
                    id="1", thread_id="t1", from_="a@b.com", subject="Unread", date="2026-01-01"
                )
            ]
            result = runner.invoke(cli, ["prompt", "unread", "emails"], input="y\n")
            assert "Do you want to run the suggested command?" in result.output
            assert "Unread" in result.output
            mock_client.list_messages.assert_called_once_with(query="is:unread", max_results=20)

    def test_yes_flag_executes_directly(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'is:unread'"
        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            mock_client.list_messages.return_value = [
                Message(
                    id="1", thread_id="t1", from_="a@b.com", subject="Unread", date="2026-01-01"
                )
            ]
            result = runner.invoke(cli, ["prompt", "unread", "emails", "--yes"])
            assert "Do you want to run the suggested command?" not in result.output
            assert "Unread" in result.output
            mock_client.list_messages.assert_called_once_with(query="is:unread", max_results=20)

    def test_empty_command_from_provider(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = ""
        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "something"])
            assert "Could not generate a command" in result.output

    def test_click_exception_handling(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail invalid-command-name"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise click.ClickException("No such command 'invalid-command-name'")

        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "Error: No such command 'invalid-command-name'" in result.output

    def test_prompt_handles_abort(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise click.Abort

        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "Operation aborted" in result.output

    def test_prompt_handles_system_exit_non_zero(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise SystemExit(1)

        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "The command exited with code 1" in result.output

    def test_prompt_handles_system_exit_zero(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise SystemExit(0)

        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert result.exit_code == 0

    def test_prompt_handles_generic_exception(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise Exception("unexpected error")

        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "Unexpected error: unexpected error" in result.output

    def test_prompt_strips_gmail_without_space(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail"
        original_main = cli.main
        inner_calls = []

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            inner_calls.append(args)
            return None

        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert result.exit_code == 0
            assert inner_calls == [[]]


class TestConfig:
    def test_show_defaults(self, runner):
        with patch.object(_cli_mod, "load_config") as mock_load:
            mock_load.return_value = ProviderConfig()
            result = runner.invoke(cli, ["config", "show"])
            assert "ollama" in result.output
            assert "http://localhost:11434" in result.output

    def test_show_with_api_key_masks(self, runner):
        with patch.object(_cli_mod, "load_config") as mock_load:
            mock_load.return_value = ProviderConfig(provider="openai", api_key="sk-secret123")
            result = runner.invoke(cli, ["config", "show"])
            assert "sk-secre" in result.output
            assert "sk-secret123" not in result.output

    def test_show_gemini(self, runner):
        with patch.object(_cli_mod, "load_config") as mock_load:
            mock_load.return_value = ProviderConfig(
                provider="gemini", api_key="secret-gemini-key-long"
            )
            result = runner.invoke(cli, ["config", "show"])
            assert "gemini" in result.output
            assert "secret-gemini-key-long" not in result.output

    def test_show_opencode_go(self, runner):
        with patch.object(_cli_mod, "load_config") as mock_load:
            mock_load.return_value = ProviderConfig(provider="opencode_go")
            result = runner.invoke(cli, ["config", "show"])
            assert "deepseek-v4-flash" in result.output

    def test_show_response_language(self, runner):
        with patch.object(_cli_mod, "load_config") as mock_load:
            mock_load.return_value = ProviderConfig(response_language="en")
            result = runner.invoke(cli, ["config", "show"])
            assert "Response language: en" in result.output

    def test_set_saves_config(self, runner):
        with (
            patch.object(_cli_mod, "save_config") as mock_save,
            patch.object(_cli_mod, "load_config") as mock_load,
        ):
            mock_load.return_value = ProviderConfig()
            result = runner.invoke(
                cli, ["config", "set", "--provider", "openai", "--api-key", "sk-test"]
            )
            assert "saved" in result.output
            saved = mock_save.call_args[0][0]
            assert saved.provider == "openai"
            assert saved.api_key == "sk-test"

    def test_set_response_language(self, runner):
        with (
            patch.object(_cli_mod, "save_config") as mock_save,
            patch.object(_cli_mod, "load_config") as mock_load,
        ):
            mock_load.return_value = ProviderConfig()
            runner.invoke(cli, ["config", "set", "--response-language", "en"])
            saved = mock_save.call_args[0][0]
            assert saved.response_language == "en"

    def test_set_ollama_url(self, runner):
        with (
            patch.object(_cli_mod, "save_config") as mock_save,
            patch.object(_cli_mod, "load_config") as mock_load,
        ):
            mock_load.return_value = ProviderConfig()
            runner.invoke(cli, ["config", "set", "--ollama-url", "http://ollama.local:8080"])
            saved = mock_save.call_args[0][0]
            assert saved.ollama_url == "http://ollama.local:8080"

    def test_set_log_days(self, runner):
        with (
            patch.object(_cli_mod, "save_config") as mock_save,
            patch.object(_cli_mod, "load_config") as mock_load,
        ):
            mock_load.return_value = ProviderConfig()
            runner.invoke(cli, ["config", "set", "--log-days", "30"])
            saved = mock_save.call_args[0][0]
            assert saved.log_days == 30


class TestExport:
    def test_show_export_json(self, runner, mock_client):
        mock_msg = Message(
            id="msg123",
            thread_id="thread456",
            from_="sender@test.com",
            subject="Test Subject",
            date="Wed, 29 Jul 2026",
            label_ids=["INBOX", "UNREAD"],
            to="recipient@test.com",
            body="This is the message body.",
        )
        mock_client.get_message.return_value = mock_msg
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            runner.isolated_filesystem(),
        ):
            result = runner.invoke(cli, ["show", "msg123", "--export", "output.json"])
            assert "exported successfully" in result.output
            assert os.path.exists("output.json")
            with open("output.json", encoding="utf-8") as f:
                data = json.load(f)
            assert data["id"] == "msg123"
            assert data["body"] == "This is the message body."

    def test_show_export_md(self, runner, mock_client):
        mock_msg = Message(
            id="msg123",
            thread_id="thread456",
            from_="sender@test.com",
            subject="Test Subject",
            date="Wed, 29 Jul 2026",
            label_ids=["INBOX", "UNREAD"],
            to="recipient@test.com",
            body="This is the message body.",
        )
        mock_client.get_message.return_value = mock_msg
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            runner.isolated_filesystem(),
        ):
            result = runner.invoke(cli, ["show", "msg123", "--export", "output.md"])
            assert "exported successfully" in result.output
            assert os.path.exists("output.md")
            with open("output.md", encoding="utf-8") as f:
                content = f.read()
            assert "# Email: Test Subject" in content
            assert "- **ID:** msg123" in content
            assert "This is the message body." in content

    def test_search_export_jsonl(self, runner, mock_client):
        mock_msgs = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            ),
            Message(
                id="msg2",
                thread_id="t2",
                from_="c@d.com",
                subject="S2",
                date="D2",
                label_ids=["L2"],
            ),
        ]
        mock_client.list_messages.return_value = mock_msgs
        mock_client.get_message.side_effect = lambda msg_id: Message(
            id=msg_id,
            thread_id=f"thread_{msg_id}",
            from_=f"sender_{msg_id}@test.com",
            subject=f"Subject {msg_id}",
            date="Date",
            label_ids=["INBOX"],
            to="recipient",
            body=f"Body {msg_id}",
        )
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            runner.isolated_filesystem(),
        ):
            result = runner.invoke(cli, ["search", "-q", "test", "--export", "output.jsonl"])
            assert "exported successfully" in result.output
            assert os.path.exists("output.jsonl")
            with open("output.jsonl", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 2
            data1 = json.loads(lines[0])
            assert data1["id"] == "msg1"
            assert data1["body"] == "Body msg1"
            data2 = json.loads(lines[1])
            assert data2["id"] == "msg2"
            assert data2["body"] == "Body msg2"

    def test_list_messages_export_default_json(self, runner, mock_client):
        mock_msgs = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            ),
        ]
        mock_client.list_messages.return_value = mock_msgs
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            runner.isolated_filesystem(),
        ):
            result = runner.invoke(cli, ["list", "messages", "--export", "output.txt"])
            assert "exported successfully" in result.output
            assert os.path.exists("output.txt.json")
            with open("output.txt.json", encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert data[0]["id"] == "msg1"
            assert data[0]["body"] == "Body1"

    def test_search_export_md_multiple(self, runner, mock_client):
        mock_msgs = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            ),
            Message(
                id="msg2",
                thread_id="t2",
                from_="c@d.com",
                subject="S2",
                date="D2",
                label_ids=["L2"],
            ),
        ]
        mock_client.list_messages.return_value = mock_msgs
        mock_client.get_message.side_effect = lambda msg_id: Message(
            id=msg_id,
            thread_id=f"thread_{msg_id}",
            from_=f"sender_{msg_id}@test.com",
            subject=f"Subject {msg_id}",
            date="Date",
            label_ids=["INBOX"],
            to="recipient",
            body=f"Body {msg_id}",
        )
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            runner.isolated_filesystem(),
        ):
            result = runner.invoke(cli, ["search", "-q", "test", "--export", "output.md"])
            assert "exported successfully" in result.output
            assert os.path.exists("output.md")
            with open("output.md", encoding="utf-8") as f:
                content = f.read()
            assert "# Email: Subject msg1" in content
            assert "\n\n---\n\n" in content
            assert "# Email: Subject msg2" in content

    def test_list_messages_classify(self, runner, mock_client):
        # Arrange
        mock_msgs = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            ),
        ]
        mock_client.list_messages.return_value = mock_msgs
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        mock_provider = MagicMock()
        mock_provider.generate_classification_report.return_value = "Ollama Classification Report"

        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            runner.isolated_filesystem(),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")

            # Act
            result = runner.invoke(cli, ["list", "messages", "--classify"])

            # Assert
            assert "Ollama Classification Report" in result.output
            mock_provider.generate_classification_report.assert_called_once()
            args, _ = mock_provider.generate_classification_report.call_args
            assert "msg1" in args[0]
            assert "Body1" in args[0]

    def test_search_classify(self, runner, mock_client):
        # Arrange
        mock_msgs = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            ),
        ]
        mock_client.list_messages.return_value = mock_msgs
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        mock_provider = MagicMock()
        mock_provider.generate_classification_report.return_value = "Gemini Classification Report"

        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            runner.isolated_filesystem(),
        ):
            mock_load.return_value = ProviderConfig(provider="gemini")

            # Act
            result = runner.invoke(cli, ["search", "-q", "test query", "--classify"])

            # Assert
            assert "Gemini Classification Report" in result.output
            mock_provider.generate_classification_report.assert_called_once()
            args, _ = mock_provider.generate_classification_report.call_args
            assert "msg1" in args[0]
            assert "Body1" in args[0]


class TestClassify:
    def _run_classify(self, runner, mock_client, mock_provider, args, raw=None):
        if raw is None:
            raw = '[{"id": "msg1", "category": "Work"}]'
        mock_provider.generate_classification_suggestions.return_value = raw
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
            runner.isolated_filesystem(),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            return runner.invoke(cli, args)

    def test_classify_with_query(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            )
        ]
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        mock_provider = MagicMock()

        result = self._run_classify(
            runner, mock_client, mock_provider, ["classify", "-q", "is:unread"]
        )

        assert result.exit_code == 0
        assert "Work" in result.output
        assert "S1" in result.output
        mock_provider.generate_classification_suggestions.assert_called_once()
        args, _ = mock_provider.generate_classification_suggestions.call_args
        assert "msg1" in args[0]

    def test_classify_by_id(self, runner, mock_client):
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        mock_provider = MagicMock()

        result = self._run_classify(
            runner, mock_client, mock_provider, ["classify", "--id", "msg1"]
        )

        assert result.exit_code == 0
        assert "Work" in result.output
        mock_client.list_messages.assert_not_called()

    def test_classify_no_messages(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        mock_provider = MagicMock()

        result = self._run_classify(runner, mock_client, mock_provider, ["classify", "-q", "nope"])

        assert result.exit_code == 0
        assert "No messages found." in result.output
        mock_provider.generate_classification_suggestions.assert_not_called()

    def test_classify_apply(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            )
        ]
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        mock_client.list_labels.return_value = []
        mock_client.create_label.return_value = {"id": "LABEL1", "name": "Work"}
        mock_provider = MagicMock()

        result = self._run_classify(
            runner, mock_client, mock_provider, ["classify", "-q", "is:unread", "--apply"]
        )

        assert result.exit_code == 0
        assert "Applied 1 suggestion(s) as labels and archived emails." in result.output
        mock_client.create_label.assert_called_once_with("Work")
        mock_client.modify_message.assert_called_once_with(
            "msg1", add_labels=["LABEL1"], remove_labels=["INBOX"]
        )

    def test_classify_apply_existing_label(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            )
        ]
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        mock_client.list_labels.return_value = [Label(id="EXIST", name="Work")]
        mock_provider = MagicMock()

        result = self._run_classify(
            runner, mock_client, mock_provider, ["classify", "-q", "is:unread", "--apply"]
        )

        assert result.exit_code == 0
        mock_client.create_label.assert_not_called()
        mock_client.modify_message.assert_called_once_with(
            "msg1", add_labels=["EXIST"], remove_labels=["INBOX"]
        )

    def test_classify_invalid_suggestions(self, runner, mock_client):
        mock_client.list_messages.return_value = [
            Message(
                id="msg1",
                thread_id="t1",
                from_="a@b.com",
                subject="S1",
                date="D1",
                label_ids=["L1"],
            )
        ]
        mock_client.get_message.return_value = Message(
            id="msg1",
            thread_id="t1",
            from_="a@b.com",
            subject="S1",
            date="D1",
            label_ids=["L1"],
            to="recip",
            body="Body1",
        )
        mock_provider = MagicMock()

        result = self._run_classify(
            runner, mock_client, mock_provider, ["classify", "-q", "x"], raw="not json at all"
        )

        assert result.exit_code == 0
        assert "Could not parse model suggestions" in result.output

    def test_classify_gmail_error(self, runner, mock_client):
        mock_client.list_messages.side_effect = GmailError("boom")
        mock_provider = MagicMock()

        result = self._run_classify(runner, mock_client, mock_provider, ["classify", "-q", "x"])

        assert result.exit_code == 0
        assert "Error: boom" in result.output


class TestParseSuggestions:
    def test_parses_plain_json(self):
        result = _cli_mod._parse_suggestions('[{"id": "1", "category": "Work"}]')
        assert result == [{"id": "1", "category": "Work"}]

    def test_parses_fenced_json(self):
        result = _cli_mod._parse_suggestions('```json\n[{"id": "1", "category": "Work"}]\n```')
        assert result == [{"id": "1", "category": "Work"}]

    def test_parses_backtick_fence(self):
        result = _cli_mod._parse_suggestions('```[{"id": "1", "category": "Work"}]```')
        assert result == [{"id": "1", "category": "Work"}]

    def test_rejects_non_array(self):
        with pytest.raises(ValueError, match="JSON array"):
            _cli_mod._parse_suggestions('{"id": "1"}')

    def test_rejects_missing_keys(self):
        with pytest.raises(ValueError, match=r"id.*category"):
            _cli_mod._parse_suggestions('[{"id": "1"}]')


class TestApplySuggestionLabels:
    def test_creates_and_applies(self):
        mock_client = MagicMock()
        mock_client.list_labels.return_value = []
        mock_client.create_label.return_value = {"id": "L1", "name": "Work"}
        suggestions = [
            {"id": "m1", "category": "Work"},
            {"id": "m2", "category": "Work"},
            {"id": "m3", "category": "Personal"},
        ]

        _cli_mod._apply_suggestion_labels(mock_client, suggestions)

        mock_client.create_label.assert_any_call("Work")
        mock_client.create_label.assert_any_call("Personal")
        assert mock_client.modify_message.call_count == 3
        args, kwargs = mock_client.modify_message.call_args
        assert args[0] == "m3"
        assert kwargs["add_labels"] == ["L1"]
        assert kwargs["remove_labels"] == ["INBOX"]

    def test_uses_existing_labels(self):
        mock_client = MagicMock()
        mock_client.list_labels.return_value = [Label(id="EXIST", name="Work")]
        suggestions = [{"id": "m1", "category": "Work"}]

        _cli_mod._apply_suggestion_labels(mock_client, suggestions)

        mock_client.create_label.assert_not_called()
        mock_client.modify_message.assert_called_once_with(
            "m1", add_labels=["EXIST"], remove_labels=["INBOX"]
        )


class TestRefreshLabels:
    def test_worker_refreshes_labels(self, mock_client):
        mock_client.list_labels.return_value = [Label(id="L1", name="Work")]
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            patch.object(_cli_mod, "refresh_labels") as mock_refresh,
        ):
            _cli_mod._refresh_labels_worker()
            mock_refresh.assert_called_once_with(mock_client)

    def test_worker_swallows_errors(self):
        with (
            patch.object(_cli_mod, "_create_client", side_effect=RuntimeError("no auth")),
            patch.object(_cli_mod, "refresh_labels") as mock_refresh,
        ):
            _cli_mod._refresh_labels_worker()
            mock_refresh.assert_not_called()

    def test_background_spawns_daemon_thread(self):
        captured = {}

        class FakeThread:
            def __init__(self, target, daemon=False):
                captured["target"] = target
                captured["daemon"] = daemon

            def start(self):
                captured["started"] = True

        with (
            patch.object(_cli_mod, "_refresh_labels_background", _REAL_REFRESH_BACKGROUND),
            patch.object(_cli_mod.threading, "Thread", FakeThread),
        ):
            _cli_mod._refresh_labels_background()
        assert captured["daemon"] is True
        assert captured["started"] is True
        assert callable(captured["target"])


class TestLogging:
    def _read_log(self, tmp_path):
        log_file = tmp_path / "logs" / "gmail-cli.log"
        return log_file.read_text(encoding="utf-8") if log_file.exists() else ""

    def test_logs_command(self, runner, mock_client, tmp_path):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["list", "messages"], mock_client)
        assert result.exit_code == 0
        assert "CMD: gmail list messages" in self._read_log(tmp_path)

    def test_logs_prompt_and_suggested(self, runner, mock_client, tmp_path):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'is:unread'"
        with (
            patch.object(_cli_mod, "load_config") as mock_load,
            patch.object(_cli_mod, "create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "unread", "emails"], input="n\n")
        assert result.exit_code == 0
        log = self._read_log(tmp_path)
        assert "PROMPT: unread emails" in log
        assert "SUGGESTED: gmail search --query 'is:unread'" in log

    def test_logs_export_directory(self, runner, mock_client, tmp_path):
        mock_msg = Message(
            id="msg123",
            thread_id="thread456",
            from_="sender@test.com",
            subject="Test Subject",
            date="Wed, 29 Jul 2026",
            label_ids=["INBOX"],
            to="recipient@test.com",
            body="body",
        )
        mock_client.get_message.return_value = mock_msg
        with (
            patch.object(_cli_mod, "_create_client", return_value=mock_client),
            runner.isolated_filesystem(),
        ):
            result = runner.invoke(cli, ["show", "msg123", "--export", "output.json"])
        assert result.exit_code == 0
        log = self._read_log(tmp_path)
        assert "Export generated at:" in log
        assert "output.json" in log

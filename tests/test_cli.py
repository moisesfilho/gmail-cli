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

    def test_create_client(self):
        with patch.object(_cli_mod, "AuthService") as mock_auth:
            mock_service = MagicMock()
            mock_auth.return_value.get_service.return_value = mock_service
            client = _create_client()
            assert isinstance(client, GmailClient)
            assert client._service is mock_service


class TestAuthLogout:
    def test_logout(self, runner):
        with patch("gmail_cli.cli.AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            result = runner.invoke(cli, ["auth", "logout"])
            assert "removido" in result.output or "Token" in result.output
            svc_instance.revoke.assert_called_once()


class TestAuthStatus:
    def test_status_authenticated(self, runner):
        with patch("gmail_cli.cli.AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            svc_instance._load_credentials.return_value = MagicMock()
            result = runner.invoke(cli, ["auth", "status"])
            assert "Autenticado" in result.output

    def test_status_credentials_found(self, runner):
        with patch("gmail_cli.cli.AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            svc_instance._load_credentials.return_value = None
            svc_instance.CREDENTIALS_FILE = "/fake/path"
            with patch("os.path.exists", return_value=True):
                result = runner.invoke(cli, ["auth", "status"])
                assert "credenciais encontradas" in result.output.lower()

    def test_status_no_credentials(self, runner):
        with patch("gmail_cli.cli.AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            svc_instance._load_credentials.return_value = None
            svc_instance.CREDENTIALS_FILE = "/fake/path"
            with patch("os.path.exists", return_value=False):
                result = runner.invoke(cli, ["auth", "status"])
                assert "Nenhuma credencial" in result.output


class TestAuthLogin:
    def test_login(self, runner):
        with patch("gmail_cli.cli.AuthService") as mock_svc:
            svc_instance = mock_svc.return_value
            result = runner.invoke(cli, ["auth", "login"])
            assert "conclu" in result.output
            svc_instance.login.assert_called_once()


class TestListMessages:
    def test_no_results(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["list", "messages"], mock_client)
        assert result.exit_code == 0
        assert "Nenhuma mensagem encontrada." in result.output

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
        assert "Nenhuma label encontrada." in result.output

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
        assert "Nenhum rascunho encontrado." in result.output
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
        assert "E-mail enviado!" in result.output

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
        assert "Label criada: L1 - Nova" in result.output

    def test_error(self, runner, mock_client):
        mock_client.create_label.side_effect = GmailError("fail")
        result = invoke(runner, ["label", "create", "X"], mock_client)
        assert "fail" in result.output


class TestLabelDelete:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["label", "delete", "L1"], mock_client)
        assert "Label L1 deletada." in result.output
        mock_client.delete_label.assert_called_once_with("L1")

    def test_error(self, runner, mock_client):
        mock_client.delete_label.side_effect = GmailError("fail")
        result = invoke(runner, ["label", "delete", "L1"], mock_client)
        assert "fail" in result.output


class TestMarkRead:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["mark", "read", "msg1"], mock_client)
        assert "Mensagem msg1 marcada como lida." in result.output
        mock_client.modify_message.assert_called_once_with("msg1", remove_labels=["UNREAD"])

    def test_error(self, runner, mock_client):
        mock_client.modify_message.side_effect = GmailError("fail")
        result = invoke(runner, ["mark", "read", "msg1"], mock_client)
        assert "fail" in result.output


class TestMarkUnread:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["mark", "unread", "msg1"], mock_client)
        assert "Mensagem msg1 marcada como não lida." in result.output
        mock_client.modify_message.assert_called_once_with("msg1", add_labels=["UNREAD"])

    def test_error(self, runner, mock_client):
        mock_client.modify_message.side_effect = GmailError("fail")
        result = invoke(runner, ["mark", "unread", "msg1"], mock_client)
        assert "fail" in result.output


class TestDelete:
    def test_trash(self, runner, mock_client):
        result = invoke(runner, ["delete", "msg1"], mock_client, input="y\n")
        assert result.exit_code == 0
        assert "movida para a lixeira" in result.output
        mock_client.trash_message.assert_called_once_with("msg1")

    def test_permanent(self, runner, mock_client):
        result = invoke(runner, ["delete", "msg1", "--permanent"], mock_client, input="y\n")
        assert result.exit_code == 0
        assert "deletada permanentemente" in result.output
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
        assert "Nenhum e-mail encontrado." in result.output

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
        assert "Deletando 2 e-mail(s)" in result.output
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
        assert "Deletando 1 e-mail(s)" in result.output
        mock_client.delete_message.assert_called_once_with("m1")
        mock_client.trash_message.assert_not_called()

    def test_error(self, runner, mock_client):
        mock_client.list_messages.side_effect = GmailError("fail")
        result = invoke(runner, ["delete-all", "-q", "from:x"], mock_client, input="y\n")
        assert "fail" in result.output


class TestRestore:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["restore", "msg1"], mock_client)
        assert "restaurada da lixeira" in result.output
        mock_client.untrash_message.assert_called_once_with("msg1")

    def test_error(self, runner, mock_client):
        mock_client.untrash_message.side_effect = GmailError("fail")
        result = invoke(runner, ["restore", "msg1"], mock_client)
        assert "fail" in result.output


class TestRestoreAll:
    def test_no_results(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["restore-all", "-q", "in:trash"], mock_client, input="y\n")
        assert "Nenhum e-mail encontrado na lixeira." in result.output

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
        assert "Restaurando 1 e-mail(s)" in result.output
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
        assert "Rascunho criado!" in result.output
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
        assert "Rascunho enviado!" in result.output
        mock_client.send_draft.assert_called_once_with("d1")

    def test_error(self, runner, mock_client):
        mock_client.send_draft.side_effect = GmailError("fail")
        result = invoke(runner, ["draft", "send", "d1"], mock_client)
        assert "fail" in result.output


class TestDraftDelete:
    def test_success(self, runner, mock_client):
        result = invoke(runner, ["draft", "delete", "d1"], mock_client)
        assert "Rascunho d1 deletado." in result.output
        mock_client.delete_draft.assert_called_once_with("d1")

    def test_error(self, runner, mock_client):
        mock_client.delete_draft.side_effect = GmailError("fail")
        result = invoke(runner, ["draft", "delete", "d1"], mock_client)
        assert "fail" in result.output


class TestAttachments:
    def test_success(self, runner, mock_client):
        mock_client.download_attachments.return_value = ["/tmp/out/doc.pdf"]
        result = invoke(runner, ["attachments", "msg1", "-o", "/tmp/out"], mock_client)
        assert "Anexo salvo: /tmp/out/doc.pdf" in result.output
        mock_client.download_attachments.assert_called_once_with("msg1", output_dir="/tmp/out")

    def test_no_files(self, runner, mock_client):
        mock_client.download_attachments.return_value = []
        result = invoke(runner, ["attachments", "msg1"], mock_client)
        assert "Nenhum anexo encontrado." in result.output

    def test_error(self, runner, mock_client):
        mock_client.download_attachments.side_effect = GmailError("fail")
        result = invoke(runner, ["attachments", "msg1"], mock_client)
        assert "fail" in result.output


class TestSearch:
    def test_no_results(self, runner, mock_client):
        mock_client.list_messages.return_value = []
        result = invoke(runner, ["search", "-q", "from:a"], mock_client)
        assert "Nenhum e-mail encontrado." in result.output

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
        with patch("gmail_cli.cli.load_config") as mock_load:
            mock_load.return_value = ProviderConfig(provider="openai")
            with patch("gmail_cli.cli.create_provider") as mock_create:
                mock_create.side_effect = ValueError("API_KEY not configured")
                result = runner.invoke(cli, ["prompt", "test"])
                assert "API_KEY" in result.output

    def test_displays_generated_command(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'from:john'"
        with patch("gmail_cli.cli.load_config") as mock_load:
            mock_load.return_value = ProviderConfig(provider="ollama")
            with patch("gmail_cli.cli.create_provider", return_value=mock_provider):
                result = runner.invoke(cli, ["prompt", "emails", "from", "john"], input="n\n")
                assert "gmail search --query 'from:john'" in result.output
                assert "Deseja executar o comando sugerido?" in result.output
                mock_provider.generate_command.assert_called_once()
                args, _ = mock_provider.generate_command.call_args
                assert args[0] == "emails from john"
                assert "Command: gmail search" in args[1]
                assert "Command: gmail prompt" not in args[1]

    def test_prompt_declines_execution(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'is:unread'"
        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli._create_client", return_value=mock_client),
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "unread", "emails"], input="n\n")
            assert "Deseja executar o comando sugerido?" in result.output
            mock_client.list_messages.assert_not_called()

    def test_prompt_accepts_execution_by_confirming(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'is:unread'"
        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli._create_client", return_value=mock_client),
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            mock_client.list_messages.return_value = [
                Message(
                    id="1", thread_id="t1", from_="a@b.com", subject="Unread", date="2026-01-01"
                )
            ]
            result = runner.invoke(cli, ["prompt", "unread", "emails"], input="y\n")
            assert "Deseja executar o comando sugerido?" in result.output
            assert "Unread" in result.output
            mock_client.list_messages.assert_called_once_with(query="is:unread", max_results=20)

    def test_yes_flag_executes_directly(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search --query 'is:unread'"
        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli._create_client", return_value=mock_client),
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            mock_client.list_messages.return_value = [
                Message(
                    id="1", thread_id="t1", from_="a@b.com", subject="Unread", date="2026-01-01"
                )
            ]
            result = runner.invoke(cli, ["prompt", "unread", "emails", "--yes"])
            assert "Deseja executar o comando sugerido?" not in result.output
            assert "Unread" in result.output
            mock_client.list_messages.assert_called_once_with(query="is:unread", max_results=20)

    def test_empty_command_from_provider(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = ""
        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "something"])
            assert "Não foi possível" in result.output

    def test_click_exception_handling(self, runner, mock_client):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail invalid-command-name"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise click.ClickException("No such command 'invalid-command-name'")

        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "Erro: No such command 'invalid-command-name'" in result.output

    def test_prompt_handles_abort(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise click.Abort

        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "Operação abortada" in result.output

    def test_prompt_handles_system_exit_non_zero(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise SystemExit(1)

        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "O comando saiu com código 1" in result.output

    def test_prompt_handles_system_exit_zero(self, runner):
        mock_provider = MagicMock()
        mock_provider.generate_command.return_value = "gmail search"
        original_main = cli.main

        def side_effect(args=None, **kwargs):
            if args and "prompt" in args:
                return original_main(args=args, **kwargs)
            raise SystemExit(0)

        with (
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
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
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert "Erro inesperado: unexpected error" in result.output

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
            patch("gmail_cli.cli.load_config") as mock_load,
            patch("gmail_cli.cli.create_provider", return_value=mock_provider),
            patch.object(cli, "main", side_effect=side_effect),
        ):
            mock_load.return_value = ProviderConfig(provider="ollama")
            result = runner.invoke(cli, ["prompt", "test", "--yes"])
            assert result.exit_code == 0
            assert inner_calls == [[]]


class TestConfig:
    def test_show_defaults(self, runner):
        with patch("gmail_cli.cli.load_config") as mock_load:
            mock_load.return_value = ProviderConfig()
            result = runner.invoke(cli, ["config", "show"])
            assert "ollama" in result.output
            assert "http://localhost:11434" in result.output

    def test_show_with_api_key_masks(self, runner):
        with patch("gmail_cli.cli.load_config") as mock_load:
            mock_load.return_value = ProviderConfig(provider="openai", api_key="sk-secret123")
            result = runner.invoke(cli, ["config", "show"])
            assert "sk-secre" in result.output
            assert "sk-secret123" not in result.output

    def test_show_gemini(self, runner):
        with patch("gmail_cli.cli.load_config") as mock_load:
            mock_load.return_value = ProviderConfig(
                provider="gemini", api_key="secret-gemini-key-long"
            )
            result = runner.invoke(cli, ["config", "show"])
            assert "gemini" in result.output
            assert "secret-gemini-key-long" not in result.output

    def test_set_saves_config(self, runner):
        with (
            patch("gmail_cli.cli.save_config") as mock_save,
            patch("gmail_cli.cli.load_config") as mock_load,
        ):
            mock_load.return_value = ProviderConfig()
            result = runner.invoke(
                cli, ["config", "set", "--provider", "openai", "--api-key", "sk-test"]
            )
            assert "salva" in result.output
            saved = mock_save.call_args[0][0]
            assert saved.provider == "openai"
            assert saved.api_key == "sk-test"

    def test_set_ollama_url(self, runner):
        with (
            patch("gmail_cli.cli.save_config") as mock_save,
            patch("gmail_cli.cli.load_config") as mock_load,
        ):
            mock_load.return_value = ProviderConfig()
            runner.invoke(cli, ["config", "set", "--ollama-url", "http://ollama.local:8080"])
            saved = mock_save.call_args[0][0]
            assert saved.ollama_url == "http://ollama.local:8080"

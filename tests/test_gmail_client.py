import base64
from unittest.mock import MagicMock, mock_open, patch

import pytest
from googleapiclient.errors import HttpError

from gmail_cli import GmailError
from gmail_cli.models import Draft, Label


def _make_http_error(status=400, message=b"error"):
    resp = MagicMock()
    resp.status = status
    return HttpError(resp, message)


class TestGmailClient:
    def test_list_messages_empty(self, gmail_client):
        gmail_client._service.users().messages().list().execute.return_value = {}
        result = gmail_client.list_messages()
        assert result == []

    def test_list_messages_with_query(self, gmail_client):
        gmail_client._service.users().messages().list().execute.return_value = {
            "messages": [{"id": "1"}]
        }
        meta_response = {
            "id": "1",
            "threadId": "t1",
            "labelIds": ["INBOX"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "a@b.com"},
                    {"name": "Subject", "value": "Test"},
                    {"name": "Date", "value": "2026-01-01"},
                ]
            },
        }
        gmail_client._service.users().messages().get().execute.return_value = meta_response

        result = gmail_client.list_messages(query="from:a@b.com", max_results=10)

        assert len(result) == 1
        assert result[0].id == "1"
        assert result[0].from_ == "a@b.com"
        assert result[0].subject == "Test"

    def test_list_messages_with_single_label(self, gmail_client):
        gmail_client._service.users().messages().list().execute.return_value = {}
        gmail_client.list_messages(label_ids="INBOX")
        call_kwargs = gmail_client._service.users().messages().list.call_args[1]
        assert call_kwargs["labelIds"] == ["INBOX"]

    def test_list_messages_http_error(self, gmail_client):
        gmail_client._service.users().messages().list().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao listar mensagens"):
            gmail_client.list_messages()

    def test_get_message(self, gmail_client):
        api_response = {
            "id": "msg1",
            "threadId": "t1",
            "labelIds": ["INBOX"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "a@b.com"},
                    {"name": "To", "value": "me@c.com"},
                    {"name": "Subject", "value": "Assunto"},
                    {"name": "Date", "value": "2026-01-01"},
                ],
                "mimeType": "text/plain",
                "body": {"data": "Q29ycG8gZG8gZS1tYWls", "size": 15},
            },
        }
        gmail_client._service.users().messages().get().execute.return_value = api_response

        msg = gmail_client.get_message("msg1")
        assert msg.id == "msg1"
        assert msg.from_ == "a@b.com"
        assert msg.to == "me@c.com"
        assert msg.subject == "Assunto"
        assert msg.body == "Corpo do e-mail"

    def test_get_message_http_error(self, gmail_client):
        gmail_client._service.users().messages().get().execute.side_effect = _make_http_error(404)
        with pytest.raises(GmailError, match="Erro ao obter mensagem"):
            gmail_client.get_message("invalid")

    def test_get_message_html_body(self, gmail_client):
        api_response = {
            "id": "msg2",
            "threadId": "t2",
            "labelIds": [],
            "payload": {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {"data": "PGgxPk9sw6E8L2gxPg=="},
                    },
                ],
                "headers": [
                    {"name": "From", "value": "a@b.com"},
                    {"name": "Subject", "value": "HTML"},
                    {"name": "Date", "value": "2026-01-01"},
                ],
            },
        }
        gmail_client._service.users().messages().get().execute.return_value = api_response
        msg = gmail_client.get_message("msg2")
        assert "<h1>Olá</h1>" in msg.body

    def test_send_message(self, gmail_client):
        gmail_client._service.users().messages().send().execute.return_value = {"id": "sent1"}
        result = gmail_client.send_message(to="b@b.com", subject="Oi", body_text="Hello")
        assert result["id"] == "sent1"

    def test_send_message_with_cc_bcc(self, gmail_client):
        gmail_client._service.users().messages().send().execute.return_value = {"id": "sent3"}
        result = gmail_client.send_message(
            to="b@b.com", subject="Cc", body_text="Test", cc="c@c.com", bcc="d@d.com"
        )
        assert result["id"] == "sent3"

    def test_send_message_with_attachment(self, gmail_client):
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=b"data")),
        ):
            gmail_client._service.users().messages().send().execute.return_value = {"id": "sent2"}
            result = gmail_client.send_message(
                to="b@b.com", subject="Com anexo", body_text="Vai", attachments=["/tmp/file.pdf"]
            )
            assert result["id"] == "sent2"

    def test_send_message_attachment_not_found(self, gmail_client):
        with (
            patch("os.path.exists", return_value=False),
            pytest.raises(FileNotFoundError, match="Anexo não encontrado"),
        ):
            gmail_client.send_message(
                to="b@b.com", subject="X", body_text="X", attachments=["/fake/file.pdf"]
            )

    def test_send_message_http_error(self, gmail_client):
        gmail_client._service.users().messages().send().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao enviar e-mail"):
            gmail_client.send_message(to="x@x.com", subject="X", body_text="X")

    @pytest.mark.parametrize(
        ("labels_response", "expected_len"),
        [
            ({"labels": [{"id": "L1", "name": "Label1"}, {"id": "L2", "name": "Label2"}]}, 2),
            ({"labels": []}, 0),
            ({}, 0),
        ],
    )
    def test_list_labels(self, gmail_client, labels_response, expected_len):
        gmail_client._service.users().labels().list().execute.return_value = labels_response
        result = gmail_client.list_labels()
        assert len(result) == expected_len
        if expected_len > 0:
            assert isinstance(result[0], Label)

    def test_list_labels_http_error(self, gmail_client):
        gmail_client._service.users().labels().list().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao listar labels"):
            gmail_client.list_labels()

    def test_create_label(self, gmail_client):
        gmail_client._service.users().labels().create().execute.return_value = {
            "id": "L1",
            "name": "Nova",
        }
        result = gmail_client.create_label("Nova")
        assert result["id"] == "L1"

    def test_create_label_http_error(self, gmail_client):
        gmail_client._service.users().labels().create().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao criar label"):
            gmail_client.create_label("X")

    def test_delete_label(self, gmail_client):
        gmail_client.delete_label("L1")
        gmail_client._service.users().labels().delete.assert_called_once_with(userId="me", id="L1")

    def test_delete_label_http_error(self, gmail_client):
        gmail_client._service.users().labels().delete().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao deletar label"):
            gmail_client.delete_label("X")

    def test_modify_message_add_labels(self, gmail_client):
        gmail_client.modify_message("msg1", add_labels=["IMPORTANT"])
        gmail_client._service.users().messages().modify.assert_called_once_with(
            userId="me", id="msg1", body={"addLabelIds": ["IMPORTANT"]}
        )

    def test_modify_message_remove_labels(self, gmail_client):
        gmail_client.modify_message("msg1", remove_labels=["UNREAD"])
        gmail_client._service.users().messages().modify.assert_called_once_with(
            userId="me", id="msg1", body={"removeLabelIds": ["UNREAD"]}
        )

    def test_modify_message_http_error(self, gmail_client):
        gmail_client._service.users().messages().modify().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao modificar mensagem"):
            gmail_client.modify_message("msg1", add_labels=["STARRED"])

    def test_list_drafts_empty(self, gmail_client):
        gmail_client._service.users().drafts().list().execute.return_value = {}
        result = gmail_client.list_drafts()
        assert result == []

    def test_list_drafts(self, gmail_client):
        gmail_client._service.users().drafts().list().execute.return_value = {
            "drafts": [{"id": "d1"}]
        }
        gmail_client._service.users().drafts().get().execute.return_value = {
            "id": "d1",
            "message": {
                "id": "m1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "eu@a.com"},
                        {"name": "Subject", "value": "Rascunho"},
                        {"name": "Date", "value": "2026-01-01"},
                    ]
                },
            },
        }
        result = gmail_client.list_drafts()
        assert len(result) == 1
        assert isinstance(result[0], Draft)
        assert result[0].subject == "Rascunho"

    def test_list_drafts_http_error(self, gmail_client):
        gmail_client._service.users().drafts().list().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao listar rascunhos"):
            gmail_client.list_drafts()

    def test_create_draft(self, gmail_client):
        gmail_client._service.users().drafts().create().execute.return_value = {"id": "d1"}
        result = gmail_client.create_draft(to="b@b.com", subject="Rasc", body_text="Corpo")
        assert result["id"] == "d1"

    def test_create_draft_with_cc(self, gmail_client):
        gmail_client._service.users().drafts().create().execute.return_value = {"id": "d2"}
        result = gmail_client.create_draft(
            to="b@b.com", subject="Rasc", body_text="Corpo", cc="c@c.com"
        )
        assert result["id"] == "d2"

    def test_create_draft_http_error(self, gmail_client):
        gmail_client._service.users().drafts().create().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao criar rascunho"):
            gmail_client.create_draft(to="a@a.com", subject="X", body_text="X")

    def test_send_draft(self, gmail_client):
        gmail_client._service.users().drafts().send().execute.return_value = {"id": "d1"}
        result = gmail_client.send_draft("d1")
        assert result["id"] == "d1"

    def test_send_draft_http_error(self, gmail_client):
        gmail_client._service.users().drafts().send().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao enviar rascunho"):
            gmail_client.send_draft("x")

    def test_delete_draft(self, gmail_client):
        gmail_client.delete_draft("d1")
        gmail_client._service.users().drafts().delete.assert_called_once_with(userId="me", id="d1")

    def test_delete_draft_http_error(self, gmail_client):
        gmail_client._service.users().drafts().delete().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao deletar rascunho"):
            gmail_client.delete_draft("x")

    def test_trash_message(self, gmail_client):
        gmail_client.trash_message("msg1")
        gmail_client._service.users().messages().trash.assert_called_once_with(
            userId="me", id="msg1"
        )

    def test_trash_message_http_error(self, gmail_client):
        gmail_client._service.users().messages().trash().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao mover para lixeira"):
            gmail_client.trash_message("x")

    def test_untrash_message(self, gmail_client):
        gmail_client.untrash_message("msg1")
        gmail_client._service.users().messages().untrash.assert_called_once_with(
            userId="me", id="msg1"
        )

    def test_untrash_message_http_error(self, gmail_client):
        gmail_client._service.users().messages().untrash().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao restaurar mensagem"):
            gmail_client.untrash_message("x")

    def test_delete_message(self, gmail_client):
        gmail_client.delete_message("msg1")
        gmail_client._service.users().messages().delete.assert_called_once_with(
            userId="me", id="msg1"
        )

    def test_delete_message_http_error(self, gmail_client):
        gmail_client._service.users().messages().delete().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao deletar mensagem"):
            gmail_client.delete_message("x")

    def test_download_attachments(self, gmail_client):
        api_response = {
            "id": "m1",
            "payload": {
                "filename": "",
                "parts": [
                    {
                        "filename": "doc.pdf",
                        "mimeType": "application/pdf",
                        "body": {"data": "ZGF0YQ==", "size": 4},
                    }
                ],
            },
        }
        gmail_client._service.users().messages().get().execute.return_value = api_response

        with patch("os.makedirs"), patch("builtins.open", mock_open()):
            files = gmail_client.download_attachments("m1", output_dir="/tmp/out")

        assert len(files) == 1
        assert "doc.pdf" in files[0]

    def test_download_attachments_with_attachment_id(self, gmail_client):
        api_response = {
            "id": "m1",
            "payload": {
                "filename": "",
                "parts": [
                    {
                        "filename": "photo.jpg",
                        "mimeType": "image/jpeg",
                        "body": {"attachmentId": "att1", "size": 100},
                    }
                ],
            },
        }
        gmail_client._service.users().messages().get().execute.return_value = api_response
        gmail_client._service.users().messages().attachments().get().execute.return_value = {
            "data": "Zm90bw=="
        }

        with patch("os.makedirs"), patch("builtins.open", mock_open()):
            files = gmail_client.download_attachments("m1", output_dir="/tmp/photos")

        assert len(files) == 1
        assert "photo.jpg" in files[0]

    def test_download_attachments_http_error(self, gmail_client):
        gmail_client._service.users().messages().get().execute.side_effect = _make_http_error()
        with pytest.raises(GmailError, match="Erro ao obter mensagem"):
            gmail_client.download_attachments("x")

    def test_download_attachments_no_files(self, gmail_client):
        gmail_client._service.users().messages().get().execute.return_value = {
            "id": "m1",
            "payload": {"filename": "", "parts": []},
        }
        with patch("os.makedirs"):
            files = gmail_client.download_attachments("m1", output_dir="/tmp/empty")
        assert files == []

    def test_extract_body_empty(self, gmail_client):
        assert gmail_client._extract_body({}) == ""

    def test_extract_body_text_plain_in_parts(self, gmail_client):
        data = base64.urlsafe_b64encode(b"plain text body").decode()
        payload = {"parts": [{"mimeType": "text/plain", "body": {"data": data}}]}
        assert gmail_client._extract_body(payload) == "plain text body"

    def test_extract_body_html_only(self, gmail_client):
        data = base64.urlsafe_b64encode(b"<p>HTML</p>").decode()
        payload = {"parts": [{"mimeType": "text/html", "body": {"data": data}}]}
        assert gmail_client._extract_body(payload) == "<p>HTML</p>"

    def test_download_attachment_data_http_error(self, gmail_client):
        api_response = {
            "id": "m1",
            "payload": {
                "filename": "",
                "parts": [
                    {
                        "filename": "fail.doc",
                        "mimeType": "application/pdf",
                        "body": {"attachmentId": "att1", "size": 10},
                    }
                ],
            },
        }
        gmail_client._service.users().messages().get().execute.return_value = api_response
        gmail_client._service.users().messages().attachments().get().execute.side_effect = (
            _make_http_error(500)
        )

        with patch("os.makedirs"):
            files = gmail_client.download_attachments("m1", output_dir="/tmp/fail")

        assert files == []

    def test_download_attachment_empty_body(self, gmail_client):
        api_response = {
            "id": "m1",
            "payload": {
                "filename": "",
                "parts": [
                    {
                        "filename": "empty.pdf",
                        "mimeType": "application/pdf",
                        "body": {},
                    }
                ],
            },
        }
        gmail_client._service.users().messages().get().execute.return_value = api_response
        with patch("os.makedirs"):
            files = gmail_client.download_attachments("m1")
        assert files == []

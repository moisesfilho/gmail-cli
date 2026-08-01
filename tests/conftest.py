import logging
import sys
from unittest.mock import MagicMock

import pytest

from gmail_cli import GmailClient, labels_cache, logging_utils
from gmail_cli.models import Draft, Label, Message

_cli_module = sys.modules["gmail_cli.cli"]


@pytest.fixture(autouse=True)
def _isolated_logger(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_utils, "LOG_FILE", tmp_path / "logs" / "gmail-cli.log")
    monkeypatch.setattr(labels_cache, "LABELS_FILE", tmp_path / "labels_cache.json")
    monkeypatch.setattr(_cli_module, "_refresh_labels_background", lambda: None)
    logger = logging.getLogger(logging_utils._LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


@pytest.fixture
def sample_message_data():
    return {
        "id": "msg123",
        "threadId": "thread123",
        "labelIds": ["INBOX", "IMPORTANT", "CATEGORY_PRIMARY"],
        "payload": {
            "headers": [
                {"name": "From", "value": "João <joao@email.com>"},
                {"name": "Subject", "value": "Teste Assunto"},
                {"name": "Date", "value": "Wed, 29 Jul 2026 10:00:00 -0300"},
                {"name": "To", "value": "eu@email.com"},
            ]
        },
    }


@pytest.fixture
def sample_message():
    return Message(
        id="msg123",
        thread_id="thread123",
        from_="João <joao@email.com>",
        subject="Teste Assunto",
        date="Wed, 29 Jul 2026 10:00:00 -0300",
        to="eu@email.com",
        body="Corpo do e-mail",
        label_ids=["INBOX", "IMPORTANT", "CATEGORY_PRIMARY"],
    )


@pytest.fixture
def sample_archived_message(sample_message):
    return Message(
        id=sample_message.id,
        thread_id=sample_message.thread_id,
        from_=sample_message.from_,
        subject=sample_message.subject,
        date=sample_message.date,
        to=sample_message.to,
        body=sample_message.body,
        label_ids=["IMPORTANT"],
    )


@pytest.fixture
def sample_trash_message(sample_message):
    return Message(
        id=sample_message.id,
        thread_id=sample_message.thread_id,
        from_=sample_message.from_,
        subject=sample_message.subject,
        date=sample_message.date,
        to=sample_message.to,
        body=sample_message.body,
        label_ids=["TRASH", "IMPORTANT"],
    )


@pytest.fixture
def sample_label():
    return Label(id="LABEL1", name="MinhaLabel")


@pytest.fixture
def sample_draft():
    return Draft(
        id="draft1",
        message_id="msg456",
        from_="eu@email.com",
        subject="Rascunho Teste",
        date="Wed, 29 Jul 2026 11:00:00 -0300",
    )


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.users().messages().list().execute.return_value = {"messages": []}
    service.users().labels().list().execute.return_value = {"labels": []}
    service.users().drafts().list().execute.return_value = {"drafts": []}
    return service


@pytest.fixture
def gmail_client(mock_service):
    return GmailClient(mock_service)

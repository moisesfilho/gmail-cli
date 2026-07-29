from gmail_cli.models import Message


class TestMessage:
    def test_is_in_inbox_true(self, sample_message):
        assert sample_message.is_in_inbox is True

    def test_is_in_inbox_false(self, sample_archived_message):
        assert sample_archived_message.is_in_inbox is False

    def test_is_in_trash_true(self, sample_trash_message):
        assert sample_trash_message.is_in_trash is True

    def test_is_in_trash_false(self, sample_message):
        assert sample_message.is_in_trash is False

    def test_is_archived(self, sample_archived_message):
        assert sample_archived_message.is_archived is True

    def test_is_archived_false_inbox(self, sample_message):
        assert sample_message.is_archived is False

    def test_is_archived_false_trash(self, sample_trash_message):
        assert sample_trash_message.is_archived is False

    def test_custom_labels_filters_system_labels(self, sample_message):
        custom = sample_message.custom_labels
        assert "IMPORTANT" in custom
        assert "INBOX" not in custom
        assert "CATEGORY_PRIMARY" not in custom

    def test_custom_labels_empty_when_only_system(self):
        msg = Message(id="x", thread_id="x", from_="a", subject="b", date="c",
                      label_ids=["INBOX", "UNREAD", "CATEGORY_SOCIAL"])
        assert msg.custom_labels == []

    def test_message_creation(self):
        msg = Message(
            id="1", thread_id="t1", from_="a@b.com",
            subject="Olá", date="2026-01-01", to="c@d.com",
            body="corpo", label_ids=["INBOX"]
        )
        assert msg.id == "1"
        assert msg.from_ == "a@b.com"
        assert msg.subject == "Olá"
        assert msg.to == "c@d.com"
        assert msg.body == "corpo"


class TestLabel:
    def test_label_creation(self, sample_label):
        assert sample_label.id == "LABEL1"
        assert sample_label.name == "MinhaLabel"


class TestDraft:
    def test_draft_creation(self, sample_draft):
        assert sample_draft.id == "draft1"
        assert sample_draft.message_id == "msg456"
        assert sample_draft.subject == "Rascunho Teste"
        assert sample_draft.from_ == "eu@email.com"

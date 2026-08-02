from gmail_cli.formatter import CliFormatter


class TestCliFormatter:
    def test_info(self, capsys):
        fmt = CliFormatter()
        fmt.info("mensagem de teste")
        captured = capsys.readouterr()
        assert captured.out.strip() == "mensagem de teste"

    def test_error(self, capsys):
        fmt = CliFormatter()
        fmt.error("erro de teste")
        captured = capsys.readouterr()
        assert "erro de teste" in captured.err

    def test_warn(self, capsys):
        fmt = CliFormatter()
        fmt.warn("aviso teste")
        captured = capsys.readouterr()
        assert "aviso teste" in captured.out

    def test_list_labels(self, capsys, sample_label):
        fmt = CliFormatter()
        fmt.list_labels([sample_label])
        captured = capsys.readouterr()
        assert sample_label.id in captured.out
        assert sample_label.name in captured.out

    def test_list_drafts(self, capsys, sample_draft):
        fmt = CliFormatter()
        fmt.list_drafts([sample_draft])
        captured = capsys.readouterr()
        assert sample_draft.id[:8] in captured.out
        assert sample_draft.subject in captured.out

    def test_show_message_inbox(self, capsys, sample_message):
        fmt = CliFormatter()
        fmt.show_message(sample_message)
        captured = capsys.readouterr()
        assert "📥 Inbox" in captured.out
        assert sample_message.from_ in captured.out
        assert sample_message.subject in captured.out
        assert sample_message.body in captured.out

    def test_show_message_archived(self, capsys, sample_archived_message):
        fmt = CliFormatter()
        fmt.show_message(sample_archived_message)
        captured = capsys.readouterr()
        assert "📦 Archived" in captured.out

    def test_show_message_trash(self, capsys, sample_trash_message):
        fmt = CliFormatter()
        fmt.show_message(sample_trash_message)
        captured = capsys.readouterr()
        assert "🗑 Trash" in captured.out

    def test_show_message_without_body(self, capsys, sample_message):
        msg = sample_message
        msg.body = ""
        fmt = CliFormatter()
        fmt.show_message(msg)
        captured = capsys.readouterr()
        assert "--- Body ---" not in captured.out

    def test_list_messages(self, capsys, sample_message):
        fmt = CliFormatter()
        fmt.list_messages([sample_message])
        captured = capsys.readouterr()
        assert "📥" in captured.out
        assert sample_message.subject in captured.out

    def test_list_suggestions(self, capsys):
        fmt = CliFormatter()
        suggestions = [
            {"id": "msg123456", "category": "Work", "subject": "Hello", "from": "a@b.com"},
            {"id": "msg7890", "category": "Personal", "subject": "Hi", "from": "c@d.com"},
        ]
        fmt.list_suggestions(suggestions)
        captured = capsys.readouterr()
        assert "CATEGORY" in captured.out
        assert "FROM" in captured.out
        assert "SUBJECT" in captured.out
        assert "Work" in captured.out
        assert "a@b.com" in captured.out
        assert "Hello" in captured.out
        assert "Personal" in captured.out
        assert "Hi" in captured.out
        assert "msg123456" not in captured.out
        assert "msg7890" not in captured.out

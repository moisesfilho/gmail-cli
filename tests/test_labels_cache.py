import json

from gmail_cli.labels_cache import label_names, load_labels, refresh_labels, save_labels
from gmail_cli.models import Label


class TestLoadLabels:
    def test_missing_file_returns_empty(self):
        assert load_labels() == []

    def test_corrupted_file_returns_empty(self, tmp_path, monkeypatch):
        labels_file = tmp_path / "labels_cache.json"
        labels_file.write_text("not json")
        monkeypatch.setattr("gmail_cli.labels_cache.LABELS_FILE", labels_file)
        assert load_labels() == []

    def test_read_error_returns_empty(self, tmp_path, monkeypatch):
        labels_file = tmp_path / "labels_cache.json"
        labels_file.mkdir()
        monkeypatch.setattr("gmail_cli.labels_cache.LABELS_FILE", labels_file)
        assert load_labels() == []

    def test_non_list_returns_empty(self, tmp_path, monkeypatch):
        labels_file = tmp_path / "labels_cache.json"
        labels_file.write_text('{"id": "x"}')
        monkeypatch.setattr("gmail_cli.labels_cache.LABELS_FILE", labels_file)
        assert load_labels() == []

    def test_filters_invalid_items(self, tmp_path, monkeypatch):
        labels_file = tmp_path / "labels_cache.json"
        labels_file.write_text(
            json.dumps([{"id": "L1", "name": "Work"}, {"id": "L2"}, "junk", {"name": "X"}])
        )
        monkeypatch.setattr("gmail_cli.labels_cache.LABELS_FILE", labels_file)
        assert load_labels() == [{"id": "L1", "name": "Work"}]


class TestLabelNames:
    def test_returns_names(self):
        assert label_names([{"id": "L1", "name": "Work"}, {"id": "L2", "name": "Personal"}]) == [
            "Work",
            "Personal",
        ]


class TestSaveLabels:
    def test_saves_and_loads(self, tmp_path, monkeypatch):
        labels_file = tmp_path / "labels_cache.json"
        monkeypatch.setattr("gmail_cli.labels_cache.LABELS_FILE", labels_file)
        labels = [{"id": "L1", "name": "Work"}]
        save_labels(labels)
        assert load_labels() == labels


class TestRefreshLabels:
    def test_persists_labels(self, tmp_path, monkeypatch):
        labels_file = tmp_path / "labels_cache.json"
        monkeypatch.setattr("gmail_cli.labels_cache.LABELS_FILE", labels_file)
        mock_client = type("C", (), {"list_labels": lambda self: [Label("L1", "Work")]})()
        result = refresh_labels(mock_client)
        assert result == [{"id": "L1", "name": "Work"}]
        assert json.loads(labels_file.read_text()) == [{"id": "L1", "name": "Work"}]

    def test_filters_hidden_labels(self, tmp_path, monkeypatch):
        labels_file = tmp_path / "labels_cache.json"
        monkeypatch.setattr("gmail_cli.labels_cache.LABELS_FILE", labels_file)
        mock_client = type(
            "C",
            (),
            {
                "list_labels": lambda self: [
                    Label("L1", "Visible", label_list_visibility="labelShow"),
                    Label("L2", "Hidden", label_list_visibility="labelHide"),
                    Label("L3", "ShowIfUnread", label_list_visibility="labelShowIfUnread"),
                    Label("L4", "System", label_list_visibility="labelShow"),
                ]
            },
        )()
        result = refresh_labels(mock_client)
        assert result == [
            {"id": "L1", "name": "Visible"},
            {"id": "L4", "name": "System"},
        ]
        assert json.loads(labels_file.read_text()) == result

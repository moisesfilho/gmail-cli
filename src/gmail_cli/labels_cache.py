import json

from .providers.config import DATA_DIR

LABELS_FILE = DATA_DIR / "labels_cache.json"


def _read_file() -> list[dict]:
    if not LABELS_FILE.exists():
        return []
    try:
        data = json.loads(LABELS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and "id" in item and "name" in item]


def load_labels() -> list[dict]:
    return _read_file()


def label_names(labels: list[dict]) -> list[str]:
    return [item["name"] for item in labels]


def save_labels(labels: list[dict]) -> None:
    LABELS_FILE.write_text(json.dumps(labels, indent=2))


def refresh_labels(client) -> list[dict]:
    labels = [
        {"id": label.id, "name": label.name}
        for label in client.list_labels()
        if label.label_list_visibility == "labelShow"
    ]
    save_labels(labels)
    return labels

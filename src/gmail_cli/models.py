from dataclasses import dataclass, field


@dataclass
class Message:
    id: str
    thread_id: str
    from_: str
    subject: str
    date: str
    label_ids: list[str] = field(default_factory=list)
    to: str = ""
    body: str = ""

    @property
    def is_in_inbox(self) -> bool:
        return "INBOX" in self.label_ids

    @property
    def is_in_trash(self) -> bool:
        return "TRASH" in self.label_ids

    @property
    def is_archived(self) -> bool:
        return not self.is_in_inbox and not self.is_in_trash

    @property
    def custom_labels(self) -> list[str]:
        skip = {"INBOX", "TRASH", "SPAM", "SENT", "DRAFT", "STARRED", "UNREAD"}
        return [
            lab for lab in self.label_ids if not lab.startswith("CATEGORY_") and lab not in skip
        ]


@dataclass
class Label:
    id: str
    name: str
    label_list_visibility: str = "labelShow"


@dataclass
class Draft:
    id: str
    message_id: str
    from_: str
    subject: str
    date: str

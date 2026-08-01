import click


class CliFormatter:
    def list_message(self, msg):
        status = "📥" if msg.is_in_inbox else "📦" if not msg.is_in_trash else "🗑"
        labels = ",".join(msg.custom_labels) if msg.custom_labels else "-"
        click.echo(
            f"{status} {msg.id[:8]}  {labels:20s}  {msg.date[:20]:20s}  "
            f"{msg.from_[:30]:30s}  {msg.subject}"
        )

    def list_messages(self, messages):
        for msg in messages:
            self.list_message(msg)

    def show_message(self, msg):
        status = (
            "📥 Inbox" if msg.is_in_inbox else "📦 Archived" if not msg.is_in_trash else "🗑 Trash"
        )
        click.echo(f"Status:  {status}")
        click.echo(f"From:    {msg.from_}")
        click.echo(f"To:      {msg.to}")
        click.echo(f"Subject: {msg.subject}")
        click.echo(f"Date:    {msg.date}")
        if msg.custom_labels:
            click.echo(f"Labels:  {', '.join(msg.custom_labels)}")
        if msg.body:
            click.echo(f"\n--- Body ---\n{msg.body}")

    def list_label(self, label):
        click.echo(f"{label.id:30s}  {label.name}")

    def list_labels(self, labels):
        for label in labels:
            self.list_label(label)

    def list_draft(self, draft):
        click.echo(
            f"{draft.id[:8]}  {draft.date[:25]:25s}  {draft.from_[:35]:35s}  {draft.subject}"
        )

    def list_drafts(self, drafts):
        for d in drafts:
            self.list_draft(d)

    def list_suggestions(self, suggestions):
        for suggestion in suggestions:
            click.echo(
                f"{suggestion['id'][:8]}  {suggestion['category']:15s}  "
                f"{suggestion.get('subject', '')}"
            )

    def info(self, message):
        click.echo(message)

    def error(self, message):
        click.echo(f"Error: {message}", err=True)

    def warn(self, message):
        click.echo(f"Warning: {message}")

#!/usr/bin/env python3
import json
import os
import shlex

import click

from .auth import AuthError, AuthService
from .formatter import CliFormatter
from .gmail_client import GmailClient, GmailError
from .logging_utils import get_logger
from .models import Message
from .providers import create_provider, load_config, save_config


def _create_client():
    return GmailClient(AuthService().get_service())


def _export_messages(messages, export_path: str):
    is_single = isinstance(messages, Message)
    msgs_list = [messages] if is_single else messages

    ext = os.path.splitext(export_path)[1].lower()

    if ext == ".json":
        data = []
        for m in msgs_list:
            data.append(
                {
                    "id": m.id,
                    "thread_id": m.thread_id,
                    "from": m.from_,
                    "to": m.to,
                    "subject": m.subject,
                    "date": m.date,
                    "label_ids": m.label_ids,
                    "body": m.body,
                }
            )
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(
                data[0] if (is_single and len(data) == 1) else data,
                f,
                indent=2,
                ensure_ascii=False,
            )
        get_logger().info("Export generated at: %s", os.path.dirname(os.path.abspath(export_path)))

    elif ext == ".jsonl":
        with open(export_path, "w", encoding="utf-8") as f:
            for m in msgs_list:
                line_data = {
                    "id": m.id,
                    "thread_id": m.thread_id,
                    "from": m.from_,
                    "to": m.to,
                    "subject": m.subject,
                    "date": m.date,
                    "label_ids": m.label_ids,
                    "body": m.body,
                }
                f.write(json.dumps(line_data, ensure_ascii=False) + "\n")
        get_logger().info("Export generated at: %s", os.path.dirname(os.path.abspath(export_path)))

    elif ext == ".md":
        with open(export_path, "w", encoding="utf-8") as f:
            for i, m in enumerate(msgs_list):
                if i > 0:
                    f.write("\n\n---\n\n")
                f.write(f"# Email: {m.subject}\n\n")
                f.write(f"- **ID:** {m.id}\n")
                f.write(f"- **Thread ID:** {m.thread_id}\n")
                f.write(f"- **From:** {m.from_}\n")
                f.write(f"- **To:** {m.to}\n")
                f.write(f"- **Date:** {m.date}\n")
                labels_str = ", ".join(m.label_ids)
                f.write(f"- **Labels:** {labels_str}\n\n")
                f.write("## Body\n\n")
                f.write(m.body or "(No Body)")
        get_logger().info("Export generated at: %s", os.path.dirname(os.path.abspath(export_path)))

    else:
        # Default to JSON
        _export_messages(messages, export_path + ".json")


def _collect_email_data(client, msgs):
    full_msgs = []
    with click.progressbar(msgs, label="Loading email data") as bar:
        for m in bar:
            full_msgs.append(client.get_message(m.id))
    data = []
    for m in full_msgs:
        data.append(
            {
                "id": m.id,
                "thread_id": m.thread_id,
                "from": m.from_,
                "to": m.to,
                "subject": m.subject,
                "date": m.date,
                "label_ids": m.label_ids,
                "body": m.body,
            }
        )
    return json.dumps(data, ensure_ascii=False), full_msgs


def _classify_messages(client, msgs):
    emails_json, _ = _collect_email_data(client, msgs)
    config = load_config()
    provider = create_provider(config)
    report = provider.generate_classification_report(emails_json)
    click.echo(report)


def _parse_suggestions(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of suggestions")
    suggestions = []
    for item in data:
        if not isinstance(item, dict) or "id" not in item or "category" not in item:
            raise ValueError("Each suggestion must have 'id' and 'category'")
        suggestions.append({"id": str(item["id"]), "category": str(item["category"])})
    return suggestions


def _apply_suggestion_labels(client, suggestions):
    labels = client.list_labels()
    existing = {label.name: label.id for label in labels}
    for category in dict.fromkeys(s["category"] for s in suggestions):
        if category not in existing:
            created = client.create_label(category)
            existing[category] = created["id"]
        label_id = existing[category]
        for suggestion in suggestions:
            if suggestion["category"] == category:
                client.modify_message(suggestion["id"], add_labels=[label_id])


fmt = CliFormatter()


class LoggingGroup(click.Group):
    def invoke(self, ctx):
        parts = list(getattr(ctx, "protected_args", ())) + list(ctx.args)
        if parts:
            get_logger().info("CMD: gmail %s", " ".join(parts))
        return super().invoke(ctx)

    def get_help(self, ctx):
        help_text = super().get_help(ctx)
        if ctx.find_root().command is self:
            help_text += "\n\n" + _build_full_reference(ctx, include_prompt=True)
        return help_text


@click.group(cls=LoggingGroup)
def cli():
    pass


@cli.group()
def auth():
    """Manage OAuth 2.0 authentication."""
    pass


@auth.command("login")
def auth_login():
    """Authenticate with Gmail (opens the browser)."""
    AuthService().login()
    fmt.info("Authentication complete! Token saved to ~/.gmail-cli/token.json")


@auth.command("logout")
def auth_logout():
    """Remove the authentication token."""
    svc = AuthService()
    svc.revoke()
    fmt.info("Token removed.")


@auth.command("status")
def auth_status():
    """Check authentication status."""
    svc = AuthService()
    if svc._load_credentials():
        fmt.info("Authenticated — token found at ~/.gmail-cli/token.json")
    elif os.path.exists(svc.CREDENTIALS_FILE):
        fmt.info("Credentials found, but token not generated yet.")
        fmt.info("Run 'gmail auth login' to authenticate.")
    else:
        fmt.info("No credentials found.")
        fmt.info("Run 'gmail auth login' to set up.")


@cli.group(name="list")
def list_cmd():
    """List resources."""
    pass


@list_cmd.command("messages")
@click.option("--query", "-q", default="", help="Filter (e.g. 'from:foo@bar.com')")
@click.option("--max", "max_results", default=20, help="Maximum number")
@click.option("--label", "-l", multiple=True, help="Filter by label")
@click.option("--export", "-e", help="Export file path (.json, .jsonl, .md)")
@click.option("--classify", "-c", is_flag=True, help="Generate an AI classification report")
def list_messages(query, max_results, label, export, classify):
    """List emails."""
    try:
        client = _create_client()
        msgs = client.list_messages(
            query=query, max_results=max_results, label_ids=list(label) or None
        )
        if not msgs:
            fmt.info("No messages found.")
            return
        if classify:
            _classify_messages(client, msgs)
        elif export:
            full_msgs = []
            with click.progressbar(msgs, label="Loading email data") as bar:
                for m in bar:
                    full_msgs.append(client.get_message(m.id))
            _export_messages(full_msgs, export)
            fmt.info(f"Data exported successfully to: {export}")
        else:
            fmt.list_messages(msgs)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@list_cmd.command("labels")
def list_labels():
    """List all labels."""
    try:
        client = _create_client()
        labels = client.list_labels()
        if not labels:
            fmt.info("No labels found.")
            return
        fmt.list_labels(labels)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@list_cmd.command("drafts")
@click.option("--max", "max_results", default=20, help="Maximum number")
def list_drafts(max_results):
    """List drafts."""
    try:
        client = _create_client()
        drafts = client.list_drafts(max_results=max_results)
        if not drafts:
            fmt.info("No drafts found.")
            return
        fmt.list_drafts(drafts)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
@click.option("--body/--no-body", default=True, help="Show body")
@click.option("--export", "-e", help="Export file path (.json, .jsonl, .md)")
def show(message_id, body, export):
    """Show email details."""
    try:
        client = _create_client()
        msg = client.get_message(message_id)
        if export:
            _export_messages(msg, export)
            fmt.info(f"Data exported successfully to: {export}")
        else:
            fmt.show_message(msg)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def send():
    """Send email."""
    pass


@send.command("message")
@click.option("--to", "-t", required=True, help="Recipient")
@click.option("--subject", "-s", required=True, help="Subject")
@click.option("--body", "-b", required=True, help="Body")
@click.option("--cc", help="Cc")
@click.option("--bcc", help="Bcc")
@click.option("--attach", "-a", multiple=True, help="Attachment (repeat)")
def send_message(to, subject, body, cc, bcc, attach):  # noqa: PLR0913, PLR0917
    """Send a new email."""
    try:
        client = _create_client()
        result = client.send_message(
            to, subject, body, cc=cc, bcc=bcc, attachments=list(attach) or None
        )
        fmt.info(f"Email sent! ID: {result['id']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def label():
    """Manage labels."""
    pass


@label.command("create")
@click.argument("name")
def create_label(name):
    """Create a new label."""
    try:
        client = _create_client()
        result = client.create_label(name)
        fmt.info(f"Label created: {result['id']} - {result['name']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@label.command("delete")
@click.argument("label_id")
def delete_label(label_id):
    """Delete a label."""
    try:
        client = _create_client()
        client.delete_label(label_id)
        fmt.info(f"Label {label_id} deleted.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def mark():
    """Mark messages."""
    pass


@mark.command("read")
@click.argument("message_id")
def mark_read(message_id):
    """Mark as read."""
    try:
        client = _create_client()
        client.modify_message(message_id, remove_labels=["UNREAD"])
        fmt.info(f"Message {message_id} marked as read.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@mark.command("unread")
@click.argument("message_id")
def mark_unread(message_id):
    """Mark as unread."""
    try:
        client = _create_client()
        client.modify_message(message_id, add_labels=["UNREAD"])
        fmt.info(f"Message {message_id} marked as unread.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
@click.option("--permanent", is_flag=True, help="Delete permanently")
@click.confirmation_option(prompt="Are you sure you want to delete this email?")
def delete(message_id, permanent):
    """Move email to trash (or --permanent)."""
    try:
        client = _create_client()
        if permanent:
            client.delete_message(message_id)
            fmt.info(f"Message {message_id} deleted permanently.")
        else:
            client.trash_message(message_id)
            fmt.info(f"Message {message_id} moved to trash.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.option("--query", "-q", required=True, help="Search filter")
@click.option("--permanent", is_flag=True, help="Delete permanently")
@click.confirmation_option(prompt="Are you sure you want to delete all emails?")
def delete_all(query, permanent):
    """Delete emails in batch."""
    try:
        client = _create_client()
        msgs = client.list_messages(query=query, max_results=None)
        if not msgs:
            fmt.info("No emails found.")
            return
        fmt.info(f"Deleting {len(msgs)} email(s)...")
        for m in msgs:
            if permanent:
                client.delete_message(m.id)
            else:
                client.trash_message(m.id)
            fmt.info(f"  {m.id[:8]} {m.subject[:60]}")
        fmt.info("Done.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
def restore(message_id):
    """Restore email from trash."""
    try:
        client = _create_client()
        client.untrash_message(message_id)
        fmt.info(f"Message {message_id} restored from trash.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.option("--query", "-q", required=True, help="Search filter")
@click.confirmation_option(prompt="Are you sure you want to restore all emails?")
def restore_all(query):
    """Restore emails from trash in batch."""
    try:
        client = _create_client()
        msgs = client.list_messages(query=query, label_ids=["TRASH"], max_results=None)
        if not msgs:
            fmt.info("No emails found in trash.")
            return
        fmt.info(f"Restoring {len(msgs)} email(s)...")
        for m in msgs:
            client.untrash_message(m.id)
            fmt.info(f"  {m.id[:8]} {m.subject[:60]}")
        fmt.info("Done.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def draft():
    """Manage drafts."""
    pass


@draft.command("create")
@click.option("--to", "-t", required=True, help="Recipient")
@click.option("--subject", "-s", required=True, help="Subject")
@click.option("--body", "-b", required=True, help="Body")
@click.option("--cc", help="Cc")
@click.option("--bcc", help="Bcc")
def create_draft(to, subject, body, cc, bcc):
    """Create a draft."""
    try:
        client = _create_client()
        result = client.create_draft(to, subject, body, cc=cc, bcc=bcc)
        fmt.info(f"Draft created! ID: {result['id']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@draft.command("send")
@click.argument("draft_id")
def send_draft(draft_id):
    """Send a draft."""
    try:
        client = _create_client()
        result = client.send_draft(draft_id)
        fmt.info(f"Draft sent! ID: {result['id']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@draft.command("delete")
@click.argument("draft_id")
def delete_draft(draft_id):
    """Delete a draft."""
    try:
        client = _create_client()
        client.delete_draft(draft_id)
        fmt.info(f"Draft {draft_id} deleted.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
@click.option("--output", "-o", default="./attachments", help="Directory")
def attachments(message_id, output):
    """Download attachments."""
    try:
        client = _create_client()
        files = client.download_attachments(message_id, output_dir=output)
        if not files:
            fmt.info("No attachments found.")
            return
        for f in files:
            fmt.info(f"Attachment saved: {f}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.option("--query", "-q", default="", help="Search term")
@click.option("--max", "max_results", default=20, help="Maximum number")
@click.option("--export", "-e", help="Export file path (.json, .jsonl, .md)")
@click.option("--classify", "-c", is_flag=True, help="Generate an AI classification report")
def search(query, max_results, export, classify):
    """Search emails."""
    try:
        client = _create_client()
        msgs = client.list_messages(query=query, max_results=max_results)
        if not msgs:
            fmt.info("No emails found.")
            return
        if classify:
            _classify_messages(client, msgs)
        elif export:
            full_msgs = []
            with click.progressbar(msgs, label="Loading email data") as bar:
                for m in bar:
                    full_msgs.append(client.get_message(m.id))
            _export_messages(full_msgs, export)
            fmt.info(f"Data exported successfully to: {export}")
        else:
            fmt.list_messages(msgs)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.option("--query", "-q", default="", help="Search filter")
@click.option("--max", "max_results", default=20, help="Maximum number")
@click.option("--id", "message_id", help="Classify a single message by ID")
@click.option("--apply", is_flag=True, help="Create suggested labels and apply them")
def classify(query, max_results, message_id, apply):
    """Suggest a classification category for each email."""
    try:
        client = _create_client()
        if message_id:
            msgs = [Message(id=message_id, thread_id="", from_="", subject="", date="")]
        else:
            msgs = client.list_messages(query=query, max_results=max_results)
            if not msgs:
                fmt.info("No messages found.")
                return
        emails_json, full_msgs = _collect_email_data(client, msgs)
        config = load_config()
        provider = create_provider(config)
        raw = provider.generate_classification_suggestions(emails_json)
        try:
            suggestions = _parse_suggestions(raw)
        except (json.JSONDecodeError, ValueError) as e:
            fmt.error(f"Could not parse model suggestions: {e}")
            return
        subject_map = {m.id: m.subject for m in full_msgs}
        for suggestion in suggestions:
            suggestion["subject"] = subject_map.get(suggestion["id"], "")
        if apply:
            _apply_suggestion_labels(client, suggestions)
            fmt.info(f"Applied {len(suggestions)} suggestion(s) as labels.")
        fmt.list_suggestions(suggestions)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def config():
    """Manage AI provider configuration."""
    pass


@config.command("show")
def config_show():
    """Show current configuration."""
    cfg = load_config()
    fmt.info(f"Provider: {cfg.provider}")
    if cfg.api_key:
        fmt.info(f"API Key: {cfg.api_key[:8]}...")
    if cfg.provider == "ollama":
        fmt.info(f"Ollama URL: {cfg.ollama_url}")
        fmt.info(f"Model: {cfg.ollama_model}")
    elif cfg.provider == "openai":
        fmt.info(f"Model: {cfg.openai_model}")
    elif cfg.provider == "gemini":
        fmt.info(f"Model: {cfg.gemini_model}")
    elif cfg.provider == "opencode_go":
        fmt.info(f"Model: {cfg.opencode_go_model}")
    fmt.info(f"Log retention (days): {cfg.log_days}")
    fmt.info(f"Response language: {cfg.response_language}")


@config.command("set")
@click.option("--provider", type=click.Choice(["openai", "gemini", "ollama", "opencode_go"]))
@click.option("--api-key")
@click.option("--ollama-url", default="http://localhost:11434")
@click.option("--ollama-model", default="llama3.2")
@click.option("--openai-model", default="gpt-4o-mini")
@click.option("--gemini-model", default="gemini-2.0-flash")
@click.option("--opencode-go-model", default="deepseek-v4-flash")
@click.option("--log-days", type=int)
@click.option("--response-language", type=click.Choice(["pt", "en"]))
def config_set(**kwargs):
    """Set configuration."""
    cfg = load_config()
    if kwargs.get("provider"):
        cfg.provider = kwargs["provider"]
    if kwargs.get("api_key"):
        cfg.api_key = kwargs["api_key"]
    cfg.ollama_url = kwargs.get("ollama_url", cfg.ollama_url)
    cfg.ollama_model = kwargs.get("ollama_model", cfg.ollama_model)
    cfg.openai_model = kwargs.get("openai_model", cfg.openai_model)
    cfg.gemini_model = kwargs.get("gemini_model", cfg.gemini_model)
    cfg.opencode_go_model = kwargs.get("opencode_go_model", cfg.opencode_go_model)
    if kwargs.get("log_days") is not None:
        cfg.log_days = kwargs["log_days"]
    if kwargs.get("response_language"):
        cfg.response_language = kwargs["response_language"]
    save_config(cfg)
    fmt.info("Configuration saved to ~/.gmail-cli/config.json")


def _build_full_reference(ctx: click.Context, include_prompt: bool = False) -> str:
    def build_help(cmd, ctx, path=None):
        if path is None:
            path = []
        name = "gmail" if not path else cmd.name
        current_path = [*path, name]
        full_name = " ".join(current_path)

        sub_ctx = ctx if not path else click.Context(cmd, info_name=name, parent=ctx)

        lines = []
        lines.append(f"Command: {full_name}")
        if isinstance(cmd, LoggingGroup):
            help_text = click.Group.get_help(cmd, sub_ctx)
        else:
            help_text = cmd.get_help(sub_ctx)
        lines.append(help_text)
        lines.append("-" * 40)

        if isinstance(cmd, click.Group):
            for sub_name, sub_cmd in cmd.commands.items():
                if sub_name == "prompt" and not include_prompt:
                    continue
                sub_help = build_help(sub_cmd, sub_ctx, current_path)
                if sub_help:
                    lines.append(sub_help)

        return "\n".join(lines)

    root_ctx = ctx.find_root()
    return build_help(root_ctx.command, root_ctx)


def _build_commands_help(ctx: click.Context) -> str:
    return _build_full_reference(ctx, include_prompt=False)


@cli.command()
@click.argument("text", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Run directly without asking for confirmation")
@click.pass_context
def prompt(ctx, text, yes):
    """Convert natural language into a gmail-cli command."""
    try:
        cfg = load_config()
        provider = create_provider(cfg)
        natural = " ".join(text)
        fmt.info(f"Generating command for: {natural}")
        get_logger().info("PROMPT: %s", natural)

        commands_help = _build_commands_help(ctx)
        generated = provider.generate_command(natural, commands_help)

        if not generated:
            fmt.error("Could not generate a command.")
            return

        get_logger().info("SUGGESTED: %s", generated)

        highlighted = click.style(generated, fg="cyan", bold=True)
        fmt.info(f"\nSuggested command: {highlighted}\n")

        should_run = yes or click.confirm("Do you want to run the suggested command?", default=True)

        if should_run:
            cmd_to_run = generated.strip()
            if cmd_to_run.startswith("gmail "):
                cmd_to_run = cmd_to_run[len("gmail ") :].strip()
            elif cmd_to_run.startswith("gmail"):
                cmd_to_run = cmd_to_run[len("gmail") :].strip()

            args_list = shlex.split(cmd_to_run)

            try:
                ctx.find_root().command.main(args=args_list, standalone_mode=False)
            except click.ClickException as e:
                fmt.error(e.format_message())
            except click.Abort:
                fmt.info("Operation aborted.")
            except SystemExit as e:
                if e.code != 0:
                    fmt.error(f"The command exited with code {e.code}")
            except Exception as e:  # noqa: BLE001
                fmt.error(f"Unexpected error: {e}")
    except (AuthError, GmailError, ValueError, ConnectionError, TimeoutError) as e:
        fmt.error(str(e))


if __name__ == "__main__":  # pragma: no cover
    cli()

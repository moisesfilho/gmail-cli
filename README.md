# gmail-cli

**Version:** `v1.0.0-alpha`
**Languages:** [English](#) | [Português](README.pt-BR.md)

CLI to manage Gmail emails, labels, drafts, and attachments from the terminal.

## Features

- **List** emails, labels, and drafts with filters
- **Show** message details (headers and body)
- **Send** email with cc, bcc, and attachments
- **Manage labels** — create and delete
- **Mark** as read / unread
- **Trash**, **permanently delete**, and **restore**
- **Batch operations** — delete/restore multiple emails by query
- **Drafts** — create, send, and delete
- **Download attachments** from a message

## Installation

```bash
pip install .
```

Development:

```bash
pip install -e ".[test,dev]"
```

## Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API**
3. Under **Credentials**, create an OAuth 2.0 credential of type "Desktop application"
4. Download the JSON and save it as `~/.gmail_cli_credentials.json`
5. Run any command to authenticate on first use

## Usage

### List emails

```bash
gmail list messages
gmail list messages -q "from:john@email.com"
gmail list messages -l INBOX --max 50
```

### Search

```bash
gmail search -q "subject:meeting"
```

### Show details

```bash
gmail show <message_id>
```

### Send email

```bash
gmail send message -t "to@email.com" -s "Subject" -b "Body"
gmail send message -t "a@b.com" -s "Hi" -b "Hello" --cc "cc@b.com" --bcc "bcc@b.com" -a ./file.pdf
```

### Labels

```bash
gmail list labels
gmail label create "MyLabel"
gmail label delete <label_id>
```

### Mark

```bash
gmail mark read <message_id>
gmail mark unread <message_id>
```

### Delete / Restore

```bash
gmail delete <message_id>
gmail delete --permanent <message_id>
gmail restore <message_id>

gmail delete-all -q "from:spam"
gmail restore-all -q "in:trash"
```

### Drafts

```bash
gmail list drafts
gmail draft create -t "a@b.com" -s "Draft" -b "Body" --cc "c@c.com"
gmail draft send <draft_id>
gmail draft delete <draft_id>
```

### Attachments

```bash
gmail attachments <message_id>
gmail attachments <message_id> -o ./downloads
```

## Project Structure

```
gmail-cli/
├── src/
│   └── gmail_cli/
│       ├── __init__.py    # Public API with __all__
│       ├── __main__.py    # python -m gmail_cli entry point
│       ├── auth.py        # OAuth 2.0 authentication (AuthService)
│       ├── cli.py         # CLI interface (click)
│       ├── formatter.py   # Output formatting (CliFormatter)
│       ├── gmail_client.py# Gmail API wrapper (GmailClient)
│       └── models.py      # Dataclasses: Message, Label, Draft
├── tests/
│   ├── conftest.py        # Shared fixtures
│   ├── test_auth.py
│   ├── test_cli.py        # Click CliRunner tests
│   ├── test_formatter.py
│   ├── test_gmail_client.py
│   └── test_models.py
├── pyproject.toml          # Config (ruff, pytest, packaging)
├── README.md               # This file
└── README.pt-BR.md         # Portuguese version
```

## Tests

```bash
pytest                    # 134 tests
pytest --cov=             # Coverage (100%)
```

## Quality

```bash
ruff check .              # Linter (0 issues)
ruff format --check .     # Formatting
bandit -r src/gmail_cli/  # SAST
```

# gmail-cli

<p>
  <img src="https://img.shields.io/badge/version-v1.2.0--alpha-blue" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/tests-189%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-100%25-brightgreen" alt="Coverage">
</p>

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

### Exporting Emails for AI/RAG

Export email details and bodies to formats optimized for LLM processing/RAG (JSON, JSONL, Markdown) using the `--export` / `-e` option with `show`, `search`, and `list messages` commands:

```bash
# Export single email details to Markdown format
gmail show <message_id> --export email.md

# Export multiple search results to JSON Lines
gmail search -q "subject:meeting" --export results.jsonl

# Export messages list to default JSON format
gmail list messages --export list.txt
```

Supported formats:
- `.json`: Standard JSON data structure.
- `.jsonl`: JSON Lines (one email object per line, ideal for vector database indexing).
- `.md`: Clean markdown document with YAML-like headers.
- Other extensions default to JSON.

### Natural Language Command Prompt

```bash
# Generate and confirm execution of a command (asks for confirmation by default)
gmail prompt "list my labels"

# Run the command directly (yes by default, bypassing confirmation)
gmail prompt "mark message 123abc as read" --yes
gmail prompt "delete emails from John" -y
```

### Provider Configuration

```bash
# View current config
gmail config show

# Use OpenAI
gmail config set --provider openai --api-key sk-xxxxx

# Use Google Gemini
gmail config set --provider gemini --api-key g-xxxxx

# Use local Ollama (default)
gmail config set --provider ollama --ollama-url http://localhost:11434

# Customize model per provider
gmail config set --openai-model gpt-4 --ollama-model llama3.1
```

Configuration is saved in `~/.gmail_cli_config.json`.
Environment variables override file config: `GMAIL_CLI_PROVIDER`, `GMAIL_CLI_API_KEY`, `GMAIL_CLI_OLLAMA_URL`, `GMAIL_CLI_OLLAMA_MODEL`, `GMAIL_CLI_OPENAI_MODEL`, `GMAIL_CLI_GEMINI_MODEL`.

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
│       ├── models.py      # Dataclasses: Message, Label, Draft
│       └── providers/     # LLM providers (OpenAI, Gemini, Ollama)
├── tests/
│   ├── conftest.py        # Shared fixtures
│   ├── test_auth.py
│   ├── test_cli.py        # Click CliRunner tests
│   ├── test_formatter.py
│   ├── test_gmail_client.py
│   ├── test_models.py
│   └── test_providers.py
├── pyproject.toml          # Config (ruff, pytest, packaging)
├── README.md               # This file
└── README.pt-BR.md         # Portuguese version
```

## Tests

```bash
pytest                    # 189 tests
pytest --cov=             # Coverage (100%)
```

## Quality

```bash
ruff check .              # Linter (0 issues)
ruff format --check .     # Formatting
bandit -r src/gmail_cli/  # SAST
```

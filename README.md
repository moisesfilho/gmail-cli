# gmail-cli

<p>
  <img src="https://img.shields.io/badge/version-v1.3.0--alpha-blue" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/tests-269%20passing-brightgreen" alt="Tests">
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
- **Batch operations** — delete/restore multiple emails by query (with pagination — handles all results)
- **Drafts** — create, send, and delete
- **Download attachments** from a message
- **AI Classification** — classify emails by category via LLM
- **Per-email classification suggestions** — `gmail classify` returns one suggested category per email (JSON) with an option to apply them as labels
- **Natural Language Prompt** — describe what you want in plain text
- **Cyclic Application Logs** — records every command, prompt, and suggested response, keeping only the configured number of days (default 120)

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
4. Download the JSON and save it as `~/.gmail-cli/credentials.json`
5. Run any command to authenticate on first use

> All configuration files are stored in `~/.gmail-cli/`:
> - `config.json` — provider settings
> - `credentials.json` — OAuth client secrets
> - `token.json` — OAuth access/refresh token (auto-generated, auto-refreshed)
> - `logs/gmail-cli.log` — cyclic application log (rotates daily, keeps `log_days`)
>
> The token is refreshed automatically when expired. Old tokens from `~/.gmail_cli_token.*` are migrated on first run.

## Usage

### Authentication

```bash
gmail auth login      # Open browser and authenticate
gmail auth status     # Check authentication status
gmail auth logout     # Revoke token and sign out
```

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

### Download attachments

```bash
gmail attachments <message_id>
gmail attachments <message_id> -o ./downloads
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

### AI Classification

Classify emails by category using your configured LLM provider:

```bash
# Classify last 20 emails
gmail list messages --classify

# Classify search results
gmail search -q "from:linkedin" --classify

# Classify with custom limit
gmail search -q "is:unread" --max 50 --classify

# Natural language (automatically picks the right command)
gmail prompt "classifique os emails do linkedin"
```

The classification report includes total count, date range, senders, and category breakdown with percentages.

### Per-email classification suggestions

Suggest a category for each email (a list or a single email):

```bash
# Suggest categories for the last 20 emails
gmail classify

# Suggest with a filter and limit
gmail classify -q "is:unread" --max 50

# Suggest for a single email
gmail classify --id <message_id>

# Create labels from suggested categories and apply them to each email
gmail classify -q "is:unread" --apply
```

The output lists `id | category | subject` for each email. With `--apply`, the suggested categories are created as labels (if they do not exist yet), each email gets its own label applied automatically, and is archived (removed from the Inbox).

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

# Use OpenCode Go (low-cost subscription)
gmail config set --provider opencode_go --api-key sk-xxxxx

# Use local Ollama (default)
gmail config set --provider ollama --ollama-url http://localhost:11434

# Customize model per provider
gmail config set --openai-model gpt-4 --ollama-model llama3.1 --opencode-go-model deepseek-v4-flash

# Set log retention in days (cyclic, deletes oldest)
gmail config set --log-days 120

# Set response language for AI-generated texts (e.g. classification report)
gmail config set --response-language en
```

Configuration is saved in `~/.gmail-cli/config.json`.
Environment variables override file config:

| Variable | Description |
|---|---|
| `GMAIL_CLI_PROVIDER` | Provider name (`openai`, `gemini`, `ollama`, `opencode_go`) |
| `GMAIL_CLI_API_KEY` | API key for OpenAI, Gemini, or OpenCode Go |
| `GMAIL_CLI_OLLAMA_URL` | Ollama server URL |
| `GMAIL_CLI_OLLAMA_MODEL` | Ollama model name |
| `GMAIL_CLI_OPENAI_MODEL` | OpenAI model name |
| `GMAIL_CLI_GEMINI_MODEL` | Gemini model name |
| `OPENCODE_GO_MODEL` | OpenCode Go model name |
| `GMAIL_CLI_LOG_DAYS` | Log retention in days (default 120) |
| `GMAIL_CLI_RESPONSE_LANGUAGE` | Language of AI-generated return texts, `pt` or `en` (default `pt`) |

### Application Logs

The CLI writes a cyclic log to `~/.gmail-cli/logs/gmail-cli.log`. It records every executed command (`CMD:`), natural language prompts and generated commands (`PROMPT:` / `SUGGESTED:`), and export directories (`Export generated at:`). The log rotates daily and old files are deleted after `log_days` days (default 120, configurable via `config set --log-days` or `GMAIL_CLI_LOG_DAYS`).

### Labels Cache

Whenever a command runs, the CLI fetches (in parallel, without blocking) all existing Gmail labels and persists them to `~/.gmail-cli/labels_cache.json`. Those labels are reused by the classification flow (`classify`, `list messages --classify`, and `search --classify`), guiding the model to suggest categories that already exist as labels.

The CLI interface and help are in English. The natural language input (`gmail prompt` and `--query`) is accepted in both Portuguese and English. AI-generated return texts (e.g. the classification report) follow the `response_language` config (`pt` or `en`).

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
│       ├── labels_cache.py # Labels cache (labels_cache.json)
│       ├── logging_utils.py # Cyclic rotating logger (TimedRotatingFileHandler)
│       ├── models.py      # Dataclasses: Message, Label, Draft
│       └── providers/     # LLM providers (OpenAI, Gemini, Ollama, OpenCodeGo)
│           ├── __init__.py
│           ├── base.py
│           ├── config.py
│           ├── gemini_provider.py
│           ├── ollama_provider.py
│           ├── openai_provider.py
│           └── opencode_go_provider.py
├── tests/
│   ├── conftest.py        # Shared fixtures
│   ├── test_auth.py
│   ├── test_cli.py        # Click CliRunner tests
│   ├── test_formatter.py
│   ├── test_gmail_client.py
│   ├── test_labels_cache.py
│   ├── test_logging_utils.py
│   ├── test_models.py
│   └── test_providers.py
├── pyproject.toml          # Config (ruff, pytest, packaging)
├── README.md               # This file
└── README.pt-BR.md         # Portuguese version
```

## Tests

```bash
pytest                    # 269 tests
pytest --cov=             # Coverage (100%)
```

## Quality

```bash
ruff check .              # Linter (0 issues)
ruff format --check .     # Formatting
bandit -r src/gmail_cli/  # SAST
```

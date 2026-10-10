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

### Versioned JSON harness

`gmail harness` also accepts version 1 JSON requests on stdin. Its stdout contains the JSON response, including structured errors; the process exit status indicates failure (2 for v1 request/global failures and 3 for partial writes). Stderr is reserved for runtime diagnostics and is not the v1 error-response channel. Existing unversioned `list`, `get`, and `mark` requests and standalone commands remain available.

List request: `{"version":1,"operation":"list","query":"","label_ids":[],"limit":50,"cursor":null}`. `limit` must be 1–100. The response contains `version`, `messages`, `next_cursor`, and `has_more`. Cursors are opaque, unsigned positions bound to normalized query/label filters; they are not authorization credentials or snapshot guarantees. Message IDs are deduplicated in Gmail order. The body prefers plain text (HTML fallback), normalizes line endings, and bounds each JSON-serialized body string (including JSON escaping) to 16 KiB and the page total to 256 KiB. Truncated messages include the marker when it fits; if it cannot fit, `body` is empty and `body_truncated` is `true`. The optional `body_truncated` field appears only when truncation occurred.

Apply request: `{"version":1,"operation":"apply","authorize":true,"archive_authorized":false,"assignments":[{"message_id":"…","labels":["Label name or ID"]}]}`. Authorization must be literal `true`; archiving requires its separate literal `true`. All messages and existing non-system labels are preflighted before writes. Apply only adds labels, is idempotent, and never creates labels; INBOX removal occurs only with archive authorization. Responses give per-item `success`, `failed`, or `not_attempted` results and a global status. A preflight failure performs no writes; remote failures may leave partial changes and are not rolled back. Exit codes are 0 for success, 2 for global/preflight failure, and 3 for partial writes. No broader OAuth scopes are requested by this protocol.

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

### External harness (JSON subprocess)

`gmail harness` reads exactly one JSON object from stdin and writes one JSON
response to stdout. It uses the existing OAuth token and Gmail client; tokens
and credential contents are never included in the protocol. The harness owns
model interpretation and decisions. Reads support `list` (query, label IDs,
limit 1–100, and allow-listed fields) and `get`; writes support only `mark`
actions `read`, `unread`, or `trash`, and require `"authorized": true` in the
request. Invalid requests and Gmail failures return a generic structured error.
No interactive confirmation is used for this explicit authorization.

```bash
printf '%s\n' '{"operation":"list","query":"is:unread","max_results":10,"fields":["id","from","subject","body"]}' | gmail harness
printf '%s\n' '{"operation":"mark","id":"MESSAGE_ID","action":"read","authorized":true}' | gmail harness
```

Each invocation is an independent subprocess. Existing standalone AI commands
remain available separately.

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

# Set request timeout in seconds (default 300)
gmail config set --request-timeout 300

# Truncate email bodies to N chars before classification (0 disables, default 1000)
gmail config set --max-body-chars 1000
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
| `GMAIL_CLI_REQUEST_TIMEOUT` | Provider request timeout in seconds (default 300) |
| `GMAIL_CLI_MAX_BODY_CHARS` | Max chars of each email body sent for classification, 0 disables (default 1000) |

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

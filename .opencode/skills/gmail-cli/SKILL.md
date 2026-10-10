---
name: gmail-cli
description: Use the gmail-cli safely and directly for Gmail retrieval, external AI classification, batch planning, applying labels, verification, or standalone AI commands. Trigger whenever an agent needs to access or modify Gmail through this project.
---

# Gmail CLI for Agents

Use this skill whenever a user asks to read, classify, label, archive, or otherwise operate on Gmail through this project. The CLI owns OAuth and Gmail API access. Do not call Gmail APIs directly, read credential files, or create helper scripts to wrap the CLI.

The old `gmail harness` command and its JSON protocol have been removed. Do not invoke or recreate them; use the `gmail batch` commands below.

## Operating rules

- Keep the user's requested scope: query, message count, and requested actions. Use `gmail batch list` for machine-readable retrieval and `gmail batch plan/apply/verify` for externally classified batches.
- `gmail batch list` is read-only. Bodies are omitted unless `--include-body` is explicitly needed for classification; included bodies are bounded to 16,000 characters per message.
- Preserve each message `id` from the list response through classification and planning. Never reconstruct IDs from subjects, senders, or dates.
- Reuse existing labels. First inspect `gmail list labels --format json`; use the exact canonical label names. For an intentional category/name mismatch, provide an explicit `label_map` in the plan input. Do not guess with fuzzy/plural matching.
- Planning is read-only. It writes a local private plan artifact but does not create labels or change Gmail messages.
- `gmail batch apply` prompts for confirmation by default. Missing labels are created only after apply confirmation. `--archive` requires an explicit user request and must be passed separately; it prompts for a distinct archive confirmation by default. Without `--archive`, the inbox state is preserved.
- Use `--yes` only when the user explicitly requests execution without confirmation interaction. It bypasses both the apply confirmation and, when `--archive` is also supplied, the archive confirmation. Never add `--yes` or `--archive` automatically. If the user has not explicitly requested confirmation-free execution and there is no interactive TTY, stop before writing and tell the user that apply requires confirmation in an interactive terminal.
- `--dry-run` performs preflight without Gmail writes or confirmation prompts, regardless of `--yes`.
- Gmail batch writes are not transactional. A failure partway through can leave a partial result; report the per-message results and do not claim rollback.
- Do not print message bodies in plan/apply/verify summaries. Keep artifacts and temporary input files local and private; do not put email bodies, OAuth data, or tokens in logs or command arguments.
- The project OAuth scope is broad (`https://mail.google.com/`). Batch limits constrain which messages the command processes, not what the OAuth credential can access.

## Recommended agent workflow

### 1. Read existing labels

```bash
gmail list labels --format json
```

The response is `{"labels":[{"id":"...","name":"...","type":"user"}]}`. Keep the exact names and IDs for resolving suggestions. The default `gmail list labels` output is a human-readable table.

### 2. Retrieve only the requested messages

For metadata-only tasks:

```bash
gmail batch list --query 'is:unread in:inbox' --max 10 --format json
```

For AI classification, request bodies only when necessary:

```bash
gmail batch list --query 'is:unread in:inbox' --max 10 --format json --include-body
```

The JSON response has a `results` array. Each row contains message IDs and metadata; `body` is present only with `--include-body`. `--max` must be between 1 and 100. Preserve the same query and max value in the subsequent plan so the CLI can check message membership.

Classify the retrieved messages using the external agent's model. Keep the classification result as data, not executable code. For each email produce its original `id` plus a category. Reuse a matching existing label; use an explicit map only when the intended canonical label is clear. If no existing label is appropriate, the plan may mark a label for creation; the CLI will create it only after interactive apply confirmation.

### 3. Create a plan from JSON data

Write a JSON data file using the agent's normal file-writing tool; this is data, not a helper script. Keep it in a private temporary location. Example input:

```json
{
  "version": 1,
  "query": "is:unread in:inbox",
  "max_results": 10,
  "messages": [
    {"id": "GMAIL_MESSAGE_ID_1", "category": "Alertas de Vaga"},
    {"id": "GMAIL_MESSAGE_ID_2", "category": "Promoções"}
  ],
  "label_map": {
    "Alertas de Vaga": "Alertas de Vagas"
  }
}
```

`label_map` is optional. Its keys are exact category strings and values are desired canonical label names. Without a mapping, the category name itself is used as the desired label. Matching normalizes Unicode, whitespace, and case, but does not infer plurals, remove accents, or fuzzy-match. The CLI rejects malformed input, duplicate IDs, IDs outside the live query result, or ambiguous label matches before writing the plan.

```bash
gmail batch plan --input /private/path/classifications.json --out /private/path/gmail-plan.json --format json
```

Plan input schema: `version` must be integer `1`; `query` a Gmail query string; `max_results` an integer from 1 to 100; `messages` an array of `{id, category}`; optional `label_map` is an object mapping category strings to target label names. Successful output includes `results` and `labels_to_create`. The artifact is versioned, atomic, mode `0600`, and contains no message bodies.

### 4. Apply only after the user requests the changes

First inspect the plan response/artifact and summarize which labels will be applied, which labels will be created, how many messages are affected, and whether archiving was requested. By default, run interactively and allow the CLI to prompt for confirmation:

```bash
gmail batch apply --plan /private/path/gmail-plan.json --format json
```

This applies labels and preserves `INBOX`. To archive, the user must have explicitly requested archiving; only then run:

```bash
gmail batch apply --plan /private/path/gmail-plan.json --format json --archive
```

By default, the command prompts for apply confirmation and, with `--archive`, a second archive confirmation. Do not proceed through either prompt without the user's explicit confirmation. If and only if the user explicitly requests execution without confirmation interaction, add `--yes`:

```bash
gmail batch apply --plan /private/path/gmail-plan.json --format json --yes
```

`--yes` bypasses both prompts, including the archive prompt when combined with `--archive`. It does not authorize archiving: only add `--archive` after a distinct explicit user request to archive, and pass it separately, for example `gmail batch apply --plan /private/path/gmail-plan.json --format json --archive --yes`. Never auto-add either flag. For a non-mutating, prompt-free preflight:

```bash
gmail batch apply --plan /private/path/gmail-plan.json --format json --dry-run
```

### 5. Verify the result

```bash
gmail batch verify --plan /private/path/gmail-plan.json --format json
```

Verification rereads current message metadata and checks expected labels and `INBOX` state from the plan. Report each message's status. Do not treat a successful apply response as a substitute for verification when the user requested verification.

## Exit codes and response handling

- `0`: command succeeded.
- `2`: invalid input/schema, failed preflight, or a refused/unavailable confirmation.
- `3`: partial write or verification mismatch.

Batch JSON responses use `results` (not `items`). `gmail list labels --format json` is the exception and uses `labels`. Parse stdout as JSON only when `--format json` is selected; errors may be emitted as JSON on stderr with the corresponding nonzero exit code. Never infer success solely from the presence of output: check the process exit code and response `status`.

## Standalone mode

Users may still use the CLI's built-in AI flow when no external harness is available:

```bash
gmail classify --query 'is:unread in:inbox' --max 10
```

This standalone command uses the configured model. Without `--apply`, it only presents suggestions. `gmail classify --apply` is a separate path: it reclassifies using the configured model and archives messages as implemented by that command. Do not substitute it for applying an already-approved external classification plan; use `gmail batch apply` for that.

## Safety checks before any write

1. Confirm the target IDs came from the requested `batch list` response and the plan query/max match that retrieval.
2. Inspect canonical label names and the plan's `labels_to_create` list.
3. Confirm the user asked for label application; require a distinct explicit request before adding `--archive`.
4. Leave `--yes` off by default. Add it only when the user explicitly requests execution without confirmation interaction; it bypasses apply and archive prompts, but does not replace the separate authorization required for `--archive`. Never auto-add either flag. If confirmation is expected, ensure the apply command is running in an interactive terminal.
5. After apply, inspect `status` and every item in `results`; if partial, report exactly which messages succeeded, failed, or were not attempted.

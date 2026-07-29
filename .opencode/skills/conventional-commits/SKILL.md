---
name: conventional-commits
description: Conventional Commits specification for commit messages. Use when creating or reviewing commit messages to ensure a clear, machine-readable git history.
---

# Conventional Commits

Every commit must follow `<type>([optional scope]): <description>`.

## Allowed Types

| Type       | Usage                        |
|-----------|------------------------------|
| `feat:`   | New feature                  |
| `fix:`    | Bug fix                      |
| `chore:`  | Tasks, deps, build scripts   |
| `test:`   | Add or fix tests             |
| `refactor:` | Production code refactor   |
| `docs:`   | Documentation only           |
| `style:`  | Formatting, lint, no logic change |
| `perf:`   | Performance improvement      |

## Rules

- Description in **imperative present tense** ("add feature", not "added feature")
- Start with **lowercase** letter
- First line under **72 characters**
- **No trailing period** on the first line
- Description must be in **English**

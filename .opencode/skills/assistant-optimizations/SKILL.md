---
name: assistant-optimizations
description: Mandatory behavior rules for the assistant — progressive disclosure instead of full directory scans, planning before coding, and a strict blocklist of directories/files to never read.
---

# Assistant Behavior Rules

## 1. Reading Restriction

Never do full directory scans (e.g. read entire `src/` folder). Use progressive disclosure: search for a signature -> ask for outline -> read only the necessary file/snippet.

## 2. Planning

For refactoring or new features, create a bullet-point plan before writing any code.

## 3. Format

Prefer Markdown tables and code blocks over raw JSON for long responses.

## Blocklist — Do NOT Read These

- Versioning: `.git/`, `.github/`, `.vscode/`, `.idea/`
- Node/TS: `node_modules/`, `dist/`, `build/`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `coverage/`
- Java/Kotlin/.NET: `bin/`, `obj/`, `target/`, `.gradle/`, `build/`, `ksp/`, `kapt/`
- Go: `vendor/`
- Logs/DB: `*.log`, `*.tmp`, `*.sql.gz`

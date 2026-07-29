---
name: semantic-versioning
description: Custom semantic versioning policy (MAJOR.MINOR.PATCH). Use when bumping versions or creating release branches.
---

# Semantic Versioning Policy

Format: `MAJOR.MINOR.PATCH` (e.g. `1.2.0`)

## Rules

- **MAJOR** — manually controlled, never auto-increment
- **MINOR** — increment on `feat:` commits; reset PATCH to 0
- **PATCH** — increment on `fix:`, `refactor:`, `perf:`, `chore:`, `style:` commits

## Release Process

1. **Release candidate** — creating `release/*` or `rc/*` branch from `develop`:
   - Bump version with `-alpha` suffix (e.g. `1.6.0-alpha`)
2. **Production** — merging RC into `main`:
   - Remove `-alpha` suffix (e.g. `1.6.0`)
3. **Git tags** — create and push `git tag v<VERSION>` and `git push --tags`

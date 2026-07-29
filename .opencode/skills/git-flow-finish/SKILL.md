---
name: git-flow-finish
description: Automates Git Flow finish (merge & branch deletion) after user approval. Use when the user says "approved", "can finish", "aprovado", "pode finalizar" or similar.
---

# Git Flow Finish Automation

When the user explicitly indicates that a feature, bugfix, or hotfix is approved, execute the Git Flow finish sequence.

## Steps

1. **Identify branch and type** — determine current branch name (e.g. `feature/foo`, `bugfix/bar`, `hotfix/critical`) and extract type + base name.

2. **Finish via Git Flow** — run the corresponding finish command:
   - Feature: `git flow feature finish <name>`
   - Bugfix: `git flow bugfix finish <name>`
   - Hotfix: `git flow hotfix finish <name>`

3. **Update remote** — push updated branches:
   - `git push origin develop`
   - For hotfixes, also: `git push origin main && git push --tags`

4. **Clean remote branch** — delete the remote branch:
   - `git push origin --delete <type>/<name>`

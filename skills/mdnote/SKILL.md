---
name: mdnote
description: Create markdown notes in $MDNOTES_ROOT. Use when the user wants to take notes, document research, or write about a code repo.
---

## Create Markdown Note

Create notes in `$MDNOTES_ROOT`, typically a cloud drive that syncs to multiple devices.

File naming: `<date>/<title>_<agentName>.md`

- Use ISO date for the folder (e.g. `2026-03-06/`).
- `<agentName>` is the name of the AI agent creating the note (e.g. `claude`, `codex`).
- Do NOT read or list other files in the output directory unless the user explicitly asks to reference them.

Each note includes a YAML frontmatter header:

- `overview`: short description of the note contents (2–3 sentences)
- `repo`: path to the relevant code repo, if applicable
- `tags`: YAML list of short tags categorizing the note. Prefer fewer — 1 tag is better than 2.
  - e.g. `tutorial`, `readme`, `doc`, `research`, `report`, `design`, `discuss`, `spec`
  - spaces allowed within a tag
  - Example:
    ```yaml
    tags:
      - spec
      - architecture
    ```

When writing about a code project:

- Search for the GitHub project URL if you are unsure.
- Prefer cloning the repo over web search.
- Use the `git-quick-clone` skill to clone to `~/<host>/<user>/<repo>`.
  - It's idempotent — you may run it without checking if the repo already exists.

```
# clones to ~/github.com/user/repo
git-quick-clone github.com/user/repo
```

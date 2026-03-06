---
name: mdnote
description: Create markdown notes in $MDNOTES_ROOT. Use when the user wants to take notes, document research, or write about a code repo.
---

## Create Markdown Note

Create notes in `$MDNOTES_ROOT`, typically a cloud drive that syncs to multiple devices.

File naming: `<date>/<time>_<title>.md`

- Use lexicographic (ISO) date and time so files sort naturally.

Each note includes a YAML frontmatter header:

- `overview`: short description of the note contents (2–3 sentences)
- `repo`: path to the relevant code repo, if applicable
- `tags`: comma-separated short tags categorizing the note
  - e.g. `tutorial`, `readme`, `doc`, `research`, `report`, `design`, `discuss`, `spec`
  - spaces allowed within a tag

When writing about a code project:

- Search for the GitHub project URL if you are unsure.
- Prefer cloning the repo over web search.
- Use the `git-quick-clone` skill to clone to `~/<host>/<user>/<repo>`.
  - It's idempotent — you may run it without checking if the repo already exists.
  - Clones to `$GITHUB_REPOS/github.com/user/repo` if `GITHUB_REPOS` is set, otherwise `github.com/user/repo` relative to CWD.

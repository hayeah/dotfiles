---
name: readme-skill
description: Generate agent-friendly README/SKILL.md for a repo. Use when the user wants to create a SKILL.md or README optimized for AI coding agents.
---

# readme-skill

Write a SKILL.md (or README.md) that is optimized for AI coding agents.

## Workflow

- Thoroughly explore the repo before writing
- Write the documentation to `README.md`
- Symlink `SKILL.md → README.md` so agent systems pick it up

## Documentation Structure

- Add YAML frontmatter for SKILL.md compliance:
  - `name` — skill identifier
  - `description` — one-liner explaining what it does and when to use it
- Provide extensive use cases and examples
  - One comment per use case explaining the scenario
- Document quirks, surprising behavior, and conventions

## Updating an Existing README

When the user asks to update a README, follow this workflow to update it incrementally based on recent changes:

- Find the commit where the README was last modified:
  - `git log -1 --format=%H -- README.md`
- Review changes since that commit:
  - `git log <last-readme-commit>..HEAD -- <subpath>`
  - `git diff <last-readme-commit>..HEAD -- <subpath>`
- Use the subpath to scope commits to only the relevant directory
  - e.g. for `skills/foo/README.md`, use `skills/foo/` as the subpath
  - If the README is at repo root, use all commits (no subpath filter)
- Review the diff, then update the README to reflect the changes

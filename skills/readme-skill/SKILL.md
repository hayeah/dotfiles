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

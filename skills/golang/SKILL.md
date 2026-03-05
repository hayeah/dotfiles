---
description: Golang style guide.
---

Golang style guide.

- Don't create internal packages unless asked.

Default project structure:

- Root package: `package <packageName>`
	- Reusable library code, designed like an SDK.
- CLI package: `cli/`
	- Subcommands, flags, etc.
	- May import from the root package.
- CLI entrypoint: `cli/<packageName>/main.go`
	- `package main`

Code Style:

- For complex features, avoid bags of loose functions 
  - Group related methods in a struct.
  - Prefer class properties over passing shared state through parameters.
- Name getters as nouns, not `get*` — e.g. `User()` not `GetUser()`.

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

## google/wire (DI)

Use [google/wire](https://github.com/google/wire) for compile-time dependency injection. Quick reference:

```bash
wire              # generate wire_gen.go in current package
wire gen ./...    # generate for all packages
wire check ./...  # validate without generating
```

- Define providers as constructors, group them with `wire.NewSet(...)`.
- Write injector stubs in `wire.go` with `//go:build wireinject`.
- Commit `wire_gen.go` to version control.

See [wire.md](wire.md) for full setup, project structure, and patterns.

Code Style:

- For complex features, avoid bags of loose functions 
  - Group related methods in a struct.
  - Prefer class properties over passing shared state through parameters.
- Name getters as nouns, not `get*` — e.g. `User()` not `GetUser()`.

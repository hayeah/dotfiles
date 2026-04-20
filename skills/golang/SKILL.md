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

## CLI parsing

Use the stdlib `flag` package. Do NOT pull in cobra, urfave/cli, kong, etc.

- Stdlib accepts both `-foo-bar` and `--foo-bar` — they're equivalent. Register flags with kebab-case names (`foo-bar`) and users get the `--foo-bar` style automatically.
- For subcommands, use `flag.NewFlagSet` per subcommand and dispatch on `os.Args[1]`.
- For short aliases, register the same variable twice:
	```go
	flag.BoolVar(&verbose, "verbose", false, "verbose output")
	flag.BoolVar(&verbose, "v", false, "verbose output (shorthand)")
	```
- Combined short flags (`-abc` for `-a -b -c`) are not supported by stdlib. Live without them.

## TOML parsing

Use [pelletier/go-toml/v2](https://github.com/pelletier/go-toml). Falls back to the field name when no tag is set, so structs stay clean. Use pointer fields to distinguish "unset" from zero. Pair with [creasty/defaults](https://github.com/creasty/defaults) for declarative defaults.

```go
import (
	"github.com/creasty/defaults"
	"github.com/pelletier/go-toml/v2"
)

type Config struct {
	Host    string `default:"localhost"`
	Port    int    `default:"8080"`
	Timeout *int   // nil = unset
}

var cfg Config
defaults.Set(&cfg)
toml.Unmarshal(data, &cfg)
```

Avoid BurntSushi/toml (requires `toml:` tags, zero-vs-unset ambiguous) and the TOML→JSON→Unmarshal trick (loses line-number errors).

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

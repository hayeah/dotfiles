# libs — Cross-Language Convention Libraries

Canonical solutions to recurring problems. Python (`hayeah-py`) is the
reference implementation; TypeScript and Go follow.

Import paths:
- Python: `from hayeah.core.<module> import ...`
- TypeScript: `import { ... } from "hayeah-ts/<module>"`
- Go: `import "github.com/hayeah/dotfiles/libs/hayeah-go/<module>"`

## logger — Structured Logging

Colored console output (stderr) + JSONL file log (`~/.local/log/<tool>.jsonl`,
5MB rotation, 3 backups). Set `LOG_LEVEL` env var to control verbosity
(debug/info/warn/error, default: info).

Python:
```python
from hayeah.core.logger import new
log = new("my-tool")
log.info("starting", port=8080, env="prod")
```

TypeScript:
```typescript
import { logger } from "hayeah-ts"
const log = logger.new("my-tool")
log.info("starting", { port: 8080 })
```

Go:
```go
import "github.com/hayeah/dotfiles/libs/hayeah-go/logger"
log := logger.New("my-tool")
log.Info("starting", "port", 8080)
```

-> [spec](hayeah-py/src/hayeah/core/logger/)

## fzfmatch — Fuzzy Path Matcher

Non-interactive, deterministic boolean filter using fzf term syntax.
No scoring — match or no match. Useful for filtering file lists,
resource names, etc. without spawning fzf.

Term syntax:
- `foo` — fuzzy substring
- `!foo` — negation (exclude matches)
- `'foo` — word boundary match
- `^foo` / `foo$` — prefix/suffix anchor
- `./` — anchors to start (like `^`)
- `foo bar` — AND (both must match, space-separated)
- `expr ; expr` — OR (union)
- `expr | expr` — AND (intersection, lower precedence)

Python:
```python
from hayeah.core.fzfmatch import parse_matcher
m = parse_matcher("src .py !test")
m.match(["src/foo.py", "src/test_foo.py", "docs/bar.md"])
# ["src/foo.py"]
```

TypeScript:
```typescript
import { parseMatcher } from "hayeah-ts/fzfmatch"
const m = parseMatcher("src .py !test")
m.match(["src/foo.py", "src/test_foo.py", "docs/bar.md"])
// ["src/foo.py"]
```

Go:
```go
import "github.com/hayeah/dotfiles/libs/hayeah-go/fzfmatch"
m, _ := fzfmatch.ParseMatcher("src .py !test")
m.Match([]string{"src/foo.py", "src/test_foo.py", "docs/bar.md"})
// ["src/foo.py"]
```

-> [spec](hayeah-py/src/hayeah/core/fzfmatch/) |
[test vectors](testdata/fzfmatch.json)

## config — Single-Envar Config

One env var per app (`<APP>_CONFIG`). Value is either a file path
(.json/.toml, detected by extension) or a JSON literal. Config values
must stay JSON-serializable.

Python:
```python
from hayeah.core.config import load
cfg = load("MY_APP_CONFIG")
print(cfg["port"])
```

TypeScript:
```typescript
import { load } from "hayeah-ts/config"
const cfg = load("MY_APP_CONFIG")
console.log(cfg.port)
```

Go:
```go
import "github.com/hayeah/dotfiles/libs/hayeah-go/config"
cfg, _ := config.Load("MY_APP_CONFIG")
fmt.Println(cfg["port"])
```

Each language also exposes `expand_env` (Go: `ExpandEnv`, TS: `expandEnv`)
for `${VAR}` interpolation in config string values. `$$` escapes a literal
`$`; bare `$` is left alone; `${VAR:-default}` falls back to `default` when
`VAR` is unset or empty (bash semantics). All three implementations share
[test vectors](testdata/expand_env.json).

```python
from hayeah.core.config import expand_env
expand_env("${HOME}/Dropbox/boss")  # "/Users/me/Dropbox/boss"
```

-> [spec](hayeah-py/src/hayeah/core/config/) |
[test vectors](testdata/single-envar-config.json) |
[expand_env vectors](testdata/expand_env.json)

## shortid — Short ID & Prefix Resolution

Two standalone functions. `generate` makes a random human-friendly ID
unique within a set (3-8 chars, safe alphabet: `0-9a-z` minus `l` and
`o`). `resolve` does prefix matching against any set of strings — short
IDs, UUIDs, SHA hashes, whatever. Shortest unambiguous prefix works.

Case-insensitive. Min query length: 3 chars.

Python:
```python
from hayeah.core.shortid import generate, resolve
existing = {"a3f", "b7k", "c2m"}
new_id = generate(existing)
resolve("a3f", ["a3f", "a3g", "b7k"])  # "a3f"
```

TypeScript:
```typescript
import { generate, resolve } from "hayeah-ts/shortid"
const existing = new Set(["a3f", "b7k", "c2m"])
const newID = generate(existing)
resolve("a3f", ["a3f", "a3g", "b7k"])  // "a3f"
```

Go:
```go
import "github.com/hayeah/dotfiles/libs/hayeah-go/shortid"
existing := map[string]bool{"a3f": true, "b7k": true}
newID, _ := shortid.Generate(existing)
result, _ := shortid.Resolve("a3f", []string{"a3f", "a3g", "b7k"})
```

-> [spec](hayeah-py/src/hayeah/core/shortid/) |
[test vectors](testdata/shortid.json)

## lstree — Sane Directory Tree Walker

Directory walker with `.gitignore` support, builtin ignores for common
language ecosystem junk (`node_modules`, `__pycache__`, `.venv` …), and
an include/exclude glob filter pipeline. Port of
[go-lstree](https://github.com/hayeah/go-lstree). Zero runtime
dependencies, Python 3.11+.

Three-stage filter pipeline: **base exclude** (`.gitignore` or builtins)
→ **include globs** (optional narrowing) → **additional exclude** (always
wins). Directory pruning happens in-place so ignored subtrees are never
entered.

Python:
```python
from hayeah.core.lstree import walk, Query
for entry in walk("src/", query=Query(globs=["**/*.py"])):
    print(entry.path)
```

TypeScript: not yet ported.

Go: use [go-lstree](https://github.com/hayeah/go-lstree) directly —
that is the reference implementation this port was derived from.

-> [spec](hayeah-py/src/hayeah/core/lstree/) |
[glob test vectors](testdata/lstree_glob.json) |
[walker test vectors](testdata/lstree.json)

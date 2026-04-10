# libs — Cross-Language Convention Libraries

Canonical solutions to recurring problems. Python (`hayeah-py`) is the
reference implementation; TypeScript and Go follow.

## logger — Structured Logging

Colored console output (stderr) + JSONL file log (`~/.local/log/<tool>.jsonl`,
5MB rotation, 3 backups). Set `LOG_LEVEL` env var to control verbosity
(debug/info/warn/error, default: info).

Python:
```python
from hayeah.core.logger import new
log = new("my-tool")
log.info("starting", port=8080, env="prod")
log.error("failed to connect", host="db.local", err=str(e))

# Bind context for all subsequent calls
log = log.bind(request_id="abc123")
log.info("handling request")  # includes request_id automatically
```

Go:
```go
log := logger.New("my-tool")
log.Info("starting", "port", 8080)
```

-> [spec](hayeah-py/src/hayeah/core/logger/)

## fzfmatch — Fuzzy Path Matcher

Non-interactive, deterministic boolean filter using fzf term syntax.
No scoring — match or no match. Useful for filtering file lists,
resource names, etc. without spawning fzf.

```python
from hayeah.core.fzfmatch import parse_matcher

m = parse_matcher("src .py !test")
m.match(["src/foo.py", "src/test_foo.py", "docs/bar.md"])
# ["src/foo.py"]
```

Term syntax:
- `foo` — fuzzy substring
- `!foo` — negation (exclude matches)
- `'foo` — word boundary match
- `^foo` / `foo$` — prefix/suffix anchor
- `./` — anchors to start (like `^`)
- `foo bar` — AND (both must match, space-separated)
- `expr ; expr` — OR (union)
- `expr | expr` — AND (intersection, lower precedence)

-> [spec](hayeah-py/src/hayeah/core/fzfmatch/) |
[test vectors](testdata/fzfmatch.json)

## config — Single-Envar Config

One env var per app (`<APP>_CONFIG`). Value is either a file path
(.json/.toml, detected by extension) or a JSON literal. Config values
must stay JSON-serializable.

```python
from hayeah.core.config import load

# Reads MY_APP_CONFIG env var:
#   "/etc/myapp/config.toml"  → loads TOML file
#   "/etc/myapp/config.json"  → loads JSON file
#   '{"port": 8080}'          → parses JSON literal
cfg = load("MY_APP_CONFIG")
print(cfg["port"])

# With a typed dataclass:
@dataclass
class AppConfig:
    port: int = 8080
    debug: bool = False

cfg = load("MY_APP_CONFIG", into=AppConfig)
print(cfg.port)
```

-> [spec](hayeah-py/src/hayeah/core/config/)

## shortid — Short ID & Prefix Resolution

Two standalone functions. `generate` makes a random human-friendly ID
unique within a set (3-8 chars, safe alphabet: `0-9a-z` minus `l` and
`o`). `resolve` does prefix matching against any set of strings — short
IDs, UUIDs, SHA hashes, whatever. Shortest unambiguous prefix works.

```python
from hayeah.core.shortid import generate, resolve

# Generate a unique short ID
existing = {"a3f", "b7k", "c2m"}
new_id = generate(existing)  # e.g. "x9p"

# Resolve prefix against any set of strings
sessions = ["a3f", "a3g", "b7k"]
resolve("a3f", sessions)  # "a3f" (exact match)
resolve("b7k", sessions)  # "b7k"

# Works on UUIDs, hashes, anything
sims = ["A1B2C3D4-E5F6-7890-...", "A1B2C3D4-FFFF-1111-...", "DEADBEEF-..."]
resolve("DEA", sims)        # "DEADBEEF-..."
resolve("A1B2C3D4-E", sims) # "A1B2C3D4-E5F6-..."
resolve("A1B", sims)        # error: ambiguous
```

Case-insensitive. Min query length: 3 chars.

-> [spec](hayeah-py/src/hayeah/core/shortid/) |
[test vectors](testdata/shortid.json)

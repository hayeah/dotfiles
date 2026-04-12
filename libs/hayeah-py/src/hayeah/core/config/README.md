# config — Single-Envar Config Loading

Load application config from a single environment variable. The env var value is interpreted as:

- **File path ending `.toml`** → load as TOML
- **File path ending `.json`** → load as JSON
- **Anything else** → parse as JSON literal

Config values must stay JSON-serializable (no datetime, no custom objects).

## API

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

## Behavior

- **Env var unset or empty** → return empty dict (or default-constructed `into` class)
- **File path, file missing** → return empty dict (or default-constructed `into` class)
- **File path, file exists** → load and parse by extension
- **JSON literal** → `json.loads()` the value directly
- **Parse error** → raise (don't silently return empty)

## Detection Logic

```
value = os.getenv(env_var)
if not value:
    return {}
if value.endswith(".toml"):
    return load_toml(value)
if value.endswith(".json"):
    return load_json(value)
return json.loads(value)  # treat as JSON literal
```

The heuristic is simple: file extensions win, everything else is JSON. No YAML support (too many footguns).

## Typed Loading (`into=`)

When `into=SomeDataclass` is provided:

- Parse the raw dict as above
- Recursively construct the dataclass from the dict
- Missing fields use dataclass defaults
- Nested dataclasses are recursively constructed
- `Path` fields get `~` expanded
- `Optional[X]` / `X | None` fields try the non-None type first

## Env Var Interpolation (`expand_env`)

A standalone helper for interpolating `${VAR}` references in config string
values. Not yet wired into `load()` — call it explicitly on values that
need expansion.

```python
from hayeah.core.config import expand_env

expand_env("${HOME}/Dropbox/boss")     # "/Users/me/Dropbox/boss"
expand_env("port: ${PORT:-7777}")      # "port: 7777" if PORT unset
expand_env("$$5 fee")                  # "$5 fee" — $$ escapes to literal $
expand_env("$FOO is literal")          # "$FOO is literal" — bare $ untouched
expand_env("${MISSING}")               # "" — missing var becomes empty
```

Rules:
- `${VAR}` → `os.environ["VAR"]`, or `""` if unset.
- `${VAR:-default}` → env value if set and non-empty, else `default` (bash `:-` semantics).
- `$$` → literal `$`.
- Bare `$` (not followed by `{`) is left as-is.
- Substitution is single-pass: the result of one expansion is not re-scanned.

The same syntax and behavior is implemented in `hayeah-go/config.ExpandEnv`
and `hayeah-ts/config.expandEnv`. Cross-language test vectors live in
`libs/testdata/expand_env.json`.

## Test Vectors

- `libs/testdata/single-envar-config.json` — `load()` cases
- `libs/testdata/expand_env.json` — `expand_env()` cases (shared with Go and TS)

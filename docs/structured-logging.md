# Structured Logging

Language-agnostic spec for structured logging across CLI tools. Each language has a shared logger package that implements this spec.

## Implementations

| Language | Package | Import |
|---|---|---|
| Python | `hayeah/` | `from hayeah import logger` |
| TypeScript | `hayeah-ts/` | `import { logger } from "hayeah-ts"` |
| Go | `golib/logger/` | `"github.com/hayeah/dotfiles/golib/logger"` |

## API

A single factory function returns a named logger:

```python
# Python
log = logger.new("tool-name")
```

```typescript
// TypeScript
const log = logger.new("tool-name");
```

```go
// Go — returns *slog.Logger
log := logger.New("tool-name")
```

- `name` identifies the tool (e.g. `"claude-notify"`, `"cloudflare-tunnel"`)
- Same name returns the same logger instance (idempotent)
- No global init step — first call configures everything

## Log Calls

Event-based, not format-string-based. First argument is a snake_case event name; remaining arguments are key-value context fields.

```python
# Python
log.info("message_sent", channel="telegram", duration_ms=120)
log.error("api_failed", status=429, retry_after=30)
```

```typescript
// TypeScript
log.info("message_sent", { channel: "telegram", duration_ms: 120 });
log.error("api_failed", { status: 429, retry_after: 30 });
```

```go
// Go (slog-style alternating key-value args)
log.Info("message_sent", "channel", "telegram", "duration_ms", 120)
log.Error("api_failed", "status", 429, "retry_after", 30)
```

### Levels

Standard levels in ascending severity: `debug`, `info`, `warn`, `error`.

Default level: `info`. Override via `LOG_LEVEL` env var (case-insensitive).

## Output

Every logger writes to two destinations simultaneously.

### Console (stderr)

Human-readable, one line per event. Colored when stderr is a TTY, plain otherwise.

```
HH:MM:SS [level    ] event_name                 key=value key2=value2
```

- Timestamp: local time, `HH:MM:SS`
- Level: left-padded in brackets
- Event: the event name string
- Fields: `key=value` pairs, space-separated

### File (JSONL)

Machine-readable, one JSON object per line. Written to `~/.local/log/<name>.jsonl`.

```json
{"timestamp":"2026-03-08T12:00:00Z","level":"info","logger":"claude-notify","event":"message_sent","channel":"telegram","duration_ms":120}
```

Required fields in every line:

- `timestamp` — ISO 8601 with timezone (UTC preferred)
- `level` — log level string
- `logger` — the logger name passed to `new()`
- `event` — the event name (first argument)

Remaining fields: all key-value pairs from the log call, serialized as JSON values (strings, numbers, booleans, null).

### File Rotation

- Max size: 5 MB per file
- Keep 3 backup files (e.g. `tool.jsonl.1`, `tool.jsonl.2`, `tool.jsonl.3`)
- Create log directory if it doesn't exist

## Bound Context

Loggers support binding persistent context that is included in every subsequent log call:

```python
# Python
log = log.bind(request_id="abc-123", user_id=42)
log.info("request_started")   # includes request_id and user_id
```

```typescript
// TypeScript — bind() returns a new Logger
const bound = log.bind({ request_id: "abc-123", user_id: 42 });
bound.info("request_started"); // includes request_id and user_id
```

```go
// Go — slog's built-in With()
bound := log.With("request_id", "abc-123", "user_id", 42)
bound.Info("request_started") // includes request_id and user_id
```

`bind()` / `With()` returns a new logger. Bound fields merge with per-call fields. Per-call fields win on conflict.

## Thread/Coroutine Context

Support context variables that propagate across the current execution context (thread, goroutine, async task):

```python
# Python — structlog contextvars
structlog.contextvars.bind_contextvars(request_id="abc-123")
log.info("handling")  # has request_id
```

```go
// Go — pass context through context.Context
ctx = logger.WithContext(ctx, "request_id", "abc-123")
log.InfoContext(ctx, "handling") // has request_id
```

This is opt-in. Implementations without coroutine-scoped context can skip this.

## Exception/Stack Logging

Error-level logs should capture stack traces when an error/exception is available:

- Console: render the traceback below the log line
- File: include `"exception"` field with the formatted stack trace string

```python
# Python
log.exception("request_failed")  # auto-captures current exception
```

```typescript
// TypeScript — pass error in fields
log.error("request_failed", { error: err }); // captures err.stack
```

```go
// Go — pass error as a value
log.Error("request_failed", "error", err)
```

## Configuration

| Setting | Source | Default |
|---|---|---|
| Log level | `LOG_LEVEL` env var | `info` |
| Log directory | Hardcoded | `~/.local/log/` |
| Console output | Always | stderr |
| Console color | Auto-detect TTY | on if TTY |
| File output | Always | enabled |
| Max file size | Hardcoded | 5 MB |
| Backup count | Hardcoded | 3 |

## Viewing Logs

```bash
# All tools — lnav (recommended)
lnav ~/.local/log/

# One tool
lnav ~/.local/log/claude-notify.jsonl

# Plain CLI
tail -f ~/.local/log/*.jsonl | jq .

# Errors only
tail -f ~/.local/log/*.jsonl | jq 'select(.level == "error")'
```

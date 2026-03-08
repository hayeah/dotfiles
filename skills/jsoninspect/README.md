---
name: jsoninspect
description: Pretty-print and colorize JSON/JSONL with string truncation. Use when inspecting large JSON files or API responses with long string fields.
---

# jsoninspect

Pretty-print and colorize JSON structure with automatic string truncation. Useful for inspecting API responses, log files, and data exports where string fields (base64 blobs, HTML, long text) would otherwise overwhelm the output.

## Install

```bash
uv tool install -e .
```

## Usage

```bash
# Inspect a JSON file
jsoninspect data.json

# Inspect a JSONL file (one JSON object per line)
jsoninspect events.jsonl

# Read from stdin
curl -s https://api.example.com/users | jsoninspect -

# Pipe from other tools
cat response.json | jsoninspect -
```

### String Truncation

Strings longer than 80 characters are truncated by default, showing an ellipsis and total character count.

```bash
# Default: truncate at 80 chars
jsoninspect data.json

# Short truncation for overview
jsoninspect data.json -s 20

# Show full strings (set very high)
jsoninspect data.json -s 999999
```

### Head and Tail

Limit output to first or last N objects — useful for large JSONL files.

```bash
# First 10 records from a JSONL file
jsoninspect logs.jsonl --head 10

# Last 5 records
jsoninspect logs.jsonl --tail 5

# Combine: first 100, then show last 3 of those
jsoninspect logs.jsonl --head 100 --tail 3
```

## Options

- `file` — Path to JSON/JSONL file, or `-` for stdin
- `--max-string`, `-s` — Max string length before truncation (default: 80)
- `--head` — Only show first N JSON objects
- `--tail` — Only show last N JSON objects

## Color Scheme

- Keys → bright magenta
- Strings → green
- Numbers → bright yellow
- Booleans → bright cyan
- Null → italic dim
- Brackets/braces → bold

## Input Handling

- Automatically detects whether input contains a single JSON value or multiple JSON objects (JSONL)
- Uses streaming JSON decoder — objects don't need to be separated by newlines; any whitespace works
- Errors and warnings are printed to stderr; JSON output goes to stdout

## Quirks

- `--head` is applied before `--tail` when both are specified
- If no file argument is given and no `-` is specified, shows help (no implicit stdin reading)
- Empty input (no JSON objects found) exits with code 1

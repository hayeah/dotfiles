---
name: tmuxcap
description: Capture tmux pane content and export as text, HTML, SVG, PNG, or JPG. Use when you need a screenshot or text dump of a tmux pane for sharing, feeding to AI, or archiving terminal state.
---

# tmuxcap

Captures the visible content of a tmux pane (including ANSI colors) and exports it to various formats. Uses `tmux capture-pane -ep` under the hood, then renders via `rich` and `Pillow`.

## Installation

```bash
cd skills/tmuxcap
uv tool install -e .
```

## Usage

```bash
tmuxcap -t <target> -o <output_file>
```

- `-t, --target` — tmux target pane (required)
- `-o, --output` — output file path; format is inferred from extension (required)

## Supported Formats

- `.txt` — plain text (ANSI stripped, TUI chars cleaned)
- `.raw` — plain text (ANSI stripped, TUI chars preserved)
- `.html` — rich HTML with inline color styles
- `.svg` — vector SVG with embedded styles
- `.png` — raster image rendered with a monospace font
- `.jpg` / `.jpeg` — same as PNG but JPEG compressed

## Target Syntax

The `-t` flag accepts any tmux target format:

- `%42` — pane ID (find with `tmux list-panes -a -F '#{pane_id}'`)
- `mysession` — active pane of a session
- `mysession:2` — active pane of window 2 in mysession
- `mysession:2.1` — pane 1 of window 2 in mysession

## Examples

```bash
# Capture a pane as a PNG screenshot for sharing with AI
tmuxcap -t %0 -o screenshot.png

# Capture as plain text for pasting into a document or prompt
tmuxcap -t %0 -o capture.txt

# Capture a specific session's active pane as HTML
tmuxcap -t mysession -o output.html

# Capture as SVG (vector, scalable)
tmuxcap -t %6 -o terminal.svg

# Capture as JPEG (smaller file size)
tmuxcap -t %6 -o capture.jpg

# List all panes to find the right target
tmux list-panes -a -F '#{pane_id} #{session_name}:#{window_index}.#{pane_index} #{pane_width}x#{pane_height} #{pane_current_command}'
```

## Color Theme

PNG/JPG image rendering remaps the base 16 ANSI colors through Rich's built-in MONOKAI terminal theme. This ensures colors are readable on the dark background — Rich's default ANSI-to-RGB mapping uses classic values (e.g. blue = `#000080`) that are invisible on dark backgrounds.

Available themes from `rich.terminal_theme`:

- `MONOKAI` — vibrant colors on near-black background (current default)
- `DIMMED_MONOKAI` — muted/desaturated variant
- `SVG_EXPORT_THEME` — used by Rich's SVG export

## Quirks and Notes

- The pane width is auto-detected via `tmux display-message` so the image matches the actual terminal layout
- PNG/JPG rendering uses Menlo (macOS), SFMono, DejaVu Sans Mono, or Liberation Mono — falls back to Pillow's default bitmap font if none are found
- Bold text with default foreground color is brightened to white
- `.txt` cleans TUI box-drawing characters by default; `.raw` preserves them
- Only captures the visible pane buffer, not scrollback history

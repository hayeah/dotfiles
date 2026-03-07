---
name: tmuxcap
description: Capture tmux pane content and export as markdown, HTML, SVG, PNG, or JPG. Use when you need a screenshot or text dump of a tmux pane for sharing, feeding to AI, or archiving terminal state.
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

- `.md` — plain text wrapped in a markdown code block (ANSI stripped)
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

# Capture as markdown for pasting into a document or prompt
tmuxcap -t %0 -o capture.md

# Capture a specific session's active pane as HTML
tmuxcap -t mysession -o output.html

# Capture as SVG (vector, scalable)
tmuxcap -t %6 -o terminal.svg

# Capture as JPEG (smaller file size)
tmuxcap -t %6 -o capture.jpg

# List all panes to find the right target
tmux list-panes -a -F '#{pane_id} #{session_name}:#{window_index}.#{pane_index} #{pane_width}x#{pane_height} #{pane_current_command}'
```

## Quirks and Notes

- The pane width is auto-detected via `tmux display-message` so the image matches the actual terminal layout
- PNG/JPG rendering uses Menlo (macOS), SFMono, DejaVu Sans Mono, or Liberation Mono — falls back to Pillow's default bitmap font if none are found
- Bold text with default foreground color is brightened to white
- The markdown format includes trailing blank lines from the pane (empty rows below content) — this matches the full pane capture
- Image background is dark gray `(30, 30, 30)` with light gray `(204, 204, 204)` default text — mimics a dark terminal theme
- Only captures the visible pane buffer, not scrollback history

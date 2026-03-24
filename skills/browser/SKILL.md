---
name: browser
description: Interactive browser automation via Chrome DevTools Protocol. Use when you need to interact with web pages, test frontends, or when user interaction with a visible browser is required.
---

# Browser

Chrome DevTools Protocol tools for agent-assisted web automation. Connects to Chrome running on `:9222` with remote debugging enabled.

## Setup

Run once before first use:

```bash
cd {baseDir}
pnpm install
pnpm link --global
```

After linking, the `browser` command is available globally.

## Start Chrome

```bash
browser start
browser start --profile
```

Launch Chrome with remote debugging on `:9222`. Use `--profile` to preserve user's authentication state (cookies, logins).

## Context Spec

A context spec describes what browser window to open. It can be:

- **TOML file** — reusable device profiles:
  ```toml
  device = "iPhone 15 Pro"
  url = "https://example.com"
  ```
- **JSON literal** — inline one-offs:
  ```
  '{"device":"iPhone 15 Pro","url":"https://example.com"}'
  ```
- **Bare URL** — desktop defaults:
  ```
  https://example.com
  ```

Spec fields: `url`, `device`, `width`, `height`, `dpr`, `mobile`, `ua`, `viewport` (WxH[@DPR]).

The `device` field resolves against Puppeteer's KnownDevices (case-insensitive prefix match). Explicit fields override device defaults.

## One-Shot Mode: `--open <spec>` (`-O`)

Opens a window, runs the command, closes the window. No session management needed. Use this for quick, single-command tasks.

```bash
browser screenshot --open https://example.com
browser screenshot --open '{"device":"iPhone 15 Pro","url":"https://example.com"}'
browser screenshot --open mobile.toml
browser content --open https://example.com
browser eval --open https://example.com 'document.title'
browser network --open https://api.example.com/dashboard --type xhr
browser a11y --open https://example.com
browser cookies --open https://example.com
browser fetch --open https://example.com https://example.com/api/data
```

Network capture in one-shot mode automatically captures from page load — no `--reload` needed.

## Persistent Sessions

For multi-step workflows (debugging, exploration, discovery), use persistent sessions. The `browser open` command holds the CDP connection alive in the foreground, preserving device emulation across commands.

**IMPORTANT**: Run `browser open` in the background. The process lifetime IS the session lifetime — when it exits, the window auto-closes.

### Open a Session

```bash
browser open https://example.com
browser open '{"device":"iPhone 15 Pro","url":"https://example.com"}'
browser open mobile.toml
```

Prints a session key (e.g. `a3f2`) to stdout. Use this key with `-s` to target the session.

### Use a Session

```bash
browser eval -s a3f2 'document.title'
browser screenshot -s a3f2
browser nav -s a3f2 https://example.com/other
browser reload -s a3f2
browser network -s a3f2 --type xhr
browser a11y -s a3f2
browser cookies -s a3f2
browser fetch -s a3f2 https://example.com/api/data
browser pick -s a3f2 "Select the login button"
```

### Close a Session

```bash
browser close -s a3f2
```

Kills the background process and closes the window.

### List Sessions

```bash
browser list
```

Output:
```
 0  [a3f2] 8CFF852B  https://example.com/ Example Domain
 1  7EFBDCDA  https://google.com  Google
*2  789D1532  https://other.com  Other
```

Sessions with keys show `[key]` labels. The `*` marks the default (latest) session.

### Legacy Session Targeting

All commands also accept `-s` with:
- Numeric index: `-s 0`, `-s 2`
- Target ID prefix: `-s 789D`, `-s 89C7`

## Navigate

```bash
browser nav https://example.com
browser nav https://example.com -s a3f2
```

Navigate the current (or specified) session to a URL in-place.

## Evaluate JavaScript

```bash
browser eval 'document.title'
browser eval 'document.querySelectorAll("a").length' -s a3f2
browser eval script.js
```

Execute JavaScript in a session. Pass inline code or a `.js`/`.mjs`/`.ts` file path. Code runs in async context. 

IMPORTANT: For scripts longer than 5–10 lines, write to a file using the `tmpfile` convention and pass the path:

```bash
# 1. generate the path
tmpfile scrape.js
# => $TMP_ROOT/2026-03-17/143052.283-scrape.js

# 2. write your script to that path (use the Write tool)

# 3. eval it
browser eval $TMP_ROOT/2026-03-17/143052.283-scrape.js -s a3f2
```

## Fetch

```bash
browser fetch https://api.example.com/data
browser fetch https://api.example.com/data -o response.json
browser fetch https://api.example.com/submit -X POST -d '{"query":"test"}' -H 'Content-Type: application/json'
```

Fetch a URL using the session's browser context (cookies, auth, origin). Runs `fetch()` inside the page, so requests inherit the session's credentials and CORS context.

Options:
- `-X <method>`: HTTP method (default: GET)
- `-H <header>`: Request header, repeatable
- `-d <body>`: Request body
- `-o <file>`: Write response body to file instead of stdout

## Screenshot

```bash
browser screenshot
browser screenshot --open '{"device":"iPhone 15 Pro","url":"https://myapp.com"}'
browser screenshot -o desktop.png
browser screenshot --full
```

Capture current viewport and return file path.

Options:
- `-o, --output <path>`: Save to specific path instead of temp file
- `--full`: Capture full scrollable page
- `-w, --wait <expr>`: JS expression to poll until truthy before capturing
- `--timeout <ms>`: Max wait time for `--wait` (default: 10000)
- `-m, --max-size <px>`: Constrain longest side and output as JPEG
- `--quality <1-100>`: JPEG quality (with `--max-size`, default: 85)

Legacy device flags (`--device`, `--viewport`, `--mobile`) still work on screenshot for backward compatibility, but prefer `--open` with a context spec.

## Screencap

Record video from a browser page. Takes rapid screenshots and pipes them to ffmpeg for video output.

```bash
browser screencap -d 5 --fps 10 -o recording.mp4
browser screencap -S '#my-widget' -d 10 --fps 15 -o widget.mp4
browser screencap --open https://myapp.com -d 5 -o demo.mp4
```

Options:
- `-d, --duration <sec>`: Recording duration in seconds (default: 5)
- `--fps <N>`: Target frame rate (default: 10, practical ceiling ~15)
- `-S, --selector <css>`: CSS selector to crop to a specific element
- `-o, --output <path>`: Output video file path (default: ./recording.mp4)
- `--quality <1-100>`: JPEG quality for frames (default: 80)
- `-w, --wait <expr>`: JS expression to poll until truthy before recording
- `--timeout <ms>`: Max wait time for `--wait` (default: 10000)

Requires ffmpeg. Uses h264_videotoolbox (macOS hardware encoder) when available, falls back to libx264.

## Pick Elements

```bash
browser pick "Click the submit button"
```

**IMPORTANT**: Use this when the user wants to select specific DOM elements on the page. Launches an interactive picker — the user clicks elements to select them (Cmd/Ctrl+Click for multiple), then presses Enter to confirm. Returns element info including tag, id, class, text, and parent hierarchy.

## Cookies

```bash
browser cookies
browser cookies --open https://example.com
```

Display all cookies for a session including domain, path, httpOnly, and secure flags.

## Network

```bash
browser network --open https://api.example.com/dashboard --type xhr
browser network --reload --type xhr --filter 'api !analytics'
browser network --reload --type xhr --dump ./responses
browser network -d 30 -s a3f2
```

Capture network requests via CDP Network domain. Listens for the specified duration (default 10s), then prints a summary. Ctrl+C stops early and still prints results.

In one-shot mode (`--open`), captures from page load automatically — no `--reload` needed.

Options:
- `--reload` / `-r`: Reload the page after starting capture
- `--duration <seconds>` / `-d`: How long to listen (default: 10)
- `--filter <string>` / `-f`: fzf-style filter on URLs. Space-separated AND, prefix `!` to negate
- `--type <type>` / `-t`: Filter by resource type: `xhr`, `doc`, `css`, `js`, `img`, `font`, `all`
- `--dump <dir>` / `-o`: Save response bodies to a directory

## Accessibility Tree

```bash
browser a11y
browser a11y --open https://example.com --depth 3
browser a11y -s a3f2
```

Dump the accessibility tree of a session. Returns a compact indented tree with roles, names, values, and key properties. Prefer this over DOM inspection when you need to understand page structure.

## Extract Page Content

```bash
browser content --open https://example.com
browser content --open https://chatgpt.com/share/<share-id>
browser content --open https://chatgpt.com/s/<post-id>
browser content https://example.com
```

Extract readable content as markdown. Uses Mozilla Readability for article extraction. Works on JavaScript-rendered pages. URL is optional with `--open` (extracts from the already-loaded page).

Auto-detects site-specific extractors:
- `chatgpt.com/share/...`: exports the full conversation as markdown from hydrated share data
- `chatgpt.com/s/...`: exports ChatGPT post conversations as markdown

## When to Use

- Testing frontend code in a real browser
- Interacting with pages that require JavaScript
- When user needs to visually see or interact with a page
- Debugging authentication or session issues
- Scraping dynamic content that requires JS execution
- Discovering API endpoints via network capture
- Taking screenshots at specific device sizes (mobile, tablet, desktop)

---

## Efficiency Guide

### Accessibility Tree Over Screenshots

**Don't** take screenshots to understand page state. **Do** use `browser a11y` first — it gives you the full semantic structure. Fall back to DOM parsing for detailed markup:

```javascript
// Get page structure
document.body.innerHTML.slice(0, 5000)

// Find interactive elements
Array.from(document.querySelectorAll('button, input, [role="button"]')).map(e => ({
  id: e.id,
  text: e.textContent.trim(),
  class: e.className
}))
```

### Complex Scripts in Single Calls

Wrap everything in an IIFE to run multi-statement code:

```javascript
(function() {
  const data = document.querySelector('#target').textContent;
  const buttons = document.querySelectorAll('button');
  buttons[0].click();
  return JSON.stringify({ data, buttonCount: buttons.length });
})()
```

### Batch Interactions

**Don't** make separate calls for each click. **Do** batch them:

```javascript
(function() {
  const actions = ["btn1", "btn2", "btn3"];
  actions.forEach(id => document.getElementById(id).click());
  return "Done";
})()
```

### Investigate Before Interacting

Always start by understanding the page structure:

```javascript
(function() {
  return {
    title: document.title,
    forms: document.forms.length,
    buttons: document.querySelectorAll('button').length,
    inputs: document.querySelectorAll('input').length,
    mainContent: document.body.innerHTML.slice(0, 3000)
  };
})()
```

Then target specific elements based on what you find.

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

## Sessions

Tabs are managed as sessions, like tmux windows. Each session has a numeric index and a stable CDP target ID. The most recently opened session is the default.

All commands accept `--session <value>` (or `-s <value>`) to target a specific session:
- By index: `-s 0`, `-s 2`
- By target ID prefix: `-s 789D`, `-s 89C7`

### List Sessions

```bash
browser list
```

Output:
```
 0  89C73DF4  https://google.com  Google
*1  789D1532  https://example.com  Example Domain
```

The `*` marks the default (latest) session.

### Open New Session

```bash
browser new https://example.com
```

Open a new tab and navigate to the URL. The new session becomes the default.

### Reload Session

```bash
browser reload
browser reload -s 0
```

### Close Session

```bash
browser close
browser close -s 0
```

## Navigate

```bash
browser nav https://example.com
browser nav https://example.com -s 0
```

Navigate the current (or specified) session to a URL in-place. Use `browser new` to open a new tab instead.

## Evaluate JavaScript

```bash
browser eval 'document.title'
browser eval 'document.querySelectorAll("a").length' -s 0
```

Execute JavaScript in a session. Code runs in async context. Use this to extract data, inspect page state, or perform DOM operations programmatically.

## Screenshot

```bash
browser screenshot
browser screenshot -s 0
```

Capture current viewport and return temporary file path. Use this to visually verify UI state.

## Pick Elements

```bash
browser pick "Click the submit button"
```

**IMPORTANT**: Use this when the user wants to select specific DOM elements on the page. Launches an interactive picker — the user clicks elements to select them (Cmd/Ctrl+Click for multiple), then presses Enter to confirm. Returns element info including tag, id, class, text, and parent hierarchy.

Common use cases:
- User says "I want to click that button" — use this to let them select it
- User says "extract data from these items" — use this to let them select the elements
- When you need specific selectors but the page structure is complex or ambiguous

## Cookies

```bash
browser cookies
browser cookies -s 0
```

Display all cookies for a session including domain, path, httpOnly, and secure flags.

## Network

```bash
browser network
browser network --reload --type xhr
browser network --reload --type xhr --filter 'api !analytics'
browser network -d 30 -s 0
```

Capture network requests on a session via CDP Network domain. Listens for the specified duration (default 10s), then prints a summary of all captured requests. Ctrl+C stops early and still prints results.

Options:
- `--reload` / `-r`: Reload the page after starting capture (ensures you catch all requests from page load)
- `--duration <seconds>` / `-d`: How long to listen (default: 10)
- `--filter <string>` / `-f`: fzf-style filter on URLs. Space-separated tokens are ANDed. Prefix with `!` to negate: `'api !google'` matches URLs containing "api" but not "google"
- `--type <type>` / `-t`: Filter by resource type: `xhr`, `doc`, `css`, `js`, `img`, `font`, `all` (default: `all`)

Output format:
```
METHOD STATUS MIME                            SIZE  URL
POST   200    application/json                   -  https://example.com/api/search
GET    200    text/css                        45KB  https://example.com/styles.css
```

Use `--type xhr --filter api` to quickly find API endpoints a page is calling.

## Accessibility Tree

```bash
browser accessibility
browser a11y --depth 3
browser a11y -s 0
```

Dump the accessibility tree of a session. Returns a compact indented tree with roles, names, values, and key properties. Use `--depth N` to limit tree depth. Use `--include-ignored` to show hidden/ignored nodes.

Prefer this over DOM inspection when you need to understand page structure, find interactive elements, or verify semantic markup. The tree is compact and structured — no need to parse raw HTML.

## Extract Page Content

```bash
browser content https://example.com
```

Navigate to a URL and extract readable content as markdown. Uses Mozilla Readability for article extraction and Turndown for HTML-to-markdown conversion. Works on JavaScript-rendered pages.

## When to Use

- Testing frontend code in a real browser
- Interacting with pages that require JavaScript
- When user needs to visually see or interact with a page
- Debugging authentication or session issues
- Scraping dynamic content that requires JS execution
- Discovering API endpoints via network capture

---

## Efficiency Guide

### Accessibility Tree Over Screenshots

**Don't** take screenshots to understand page state. **Do** use `browser a11y` first — it gives you the full semantic structure with roles, labels, and interactive elements in a compact tree. Fall back to DOM parsing for detailed markup:

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

### Waiting for Updates

If DOM updates after actions, add a small delay:

```bash
sleep 0.5 && browser eval '...'
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

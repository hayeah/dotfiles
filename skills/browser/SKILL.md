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
```

## Start Chrome

```bash
pnpm --silent --prefix {baseDir} browser start
pnpm --silent --prefix {baseDir} browser start --profile
```

Launch Chrome with remote debugging on `:9222`. Use `--profile` to preserve user's authentication state (cookies, logins).

## Navigate

```bash
pnpm --silent --prefix {baseDir} browser nav https://example.com
pnpm --silent --prefix {baseDir} browser nav https://example.com --new
pnpm --silent --prefix {baseDir} browser nav https://example.com --reload
```

Navigate to URLs. Use `--new` to open in a new tab, `--reload` to force reload.

## Evaluate JavaScript

```bash
pnpm --silent --prefix {baseDir} browser eval 'document.title'
pnpm --silent --prefix {baseDir} browser eval 'document.querySelectorAll("a").length'
```

Execute JavaScript in the active tab. Code runs in async context. Use this to extract data, inspect page state, or perform DOM operations programmatically.

## Screenshot

```bash
pnpm --silent --prefix {baseDir} browser screenshot
```

Capture current viewport and return temporary file path. Use this to visually verify UI state.

## Pick Elements

```bash
pnpm --silent --prefix {baseDir} browser pick "Click the submit button"
```

**IMPORTANT**: Use this when the user wants to select specific DOM elements on the page. Launches an interactive picker — the user clicks elements to select them (Cmd/Ctrl+Click for multiple), then presses Enter to confirm. Returns element info including tag, id, class, text, and parent hierarchy.

Common use cases:
- User says "I want to click that button" — use this to let them select it
- User says "extract data from these items" — use this to let them select the elements
- When you need specific selectors but the page structure is complex or ambiguous

## Cookies

```bash
pnpm --silent --prefix {baseDir} browser cookies
```

Display all cookies for the current tab including domain, path, httpOnly, and secure flags.

## Extract Page Content

```bash
pnpm --silent --prefix {baseDir} browser content https://example.com
```

Navigate to a URL and extract readable content as markdown. Uses Mozilla Readability for article extraction and Turndown for HTML-to-markdown conversion. Works on JavaScript-rendered pages.

## When to Use

- Testing frontend code in a real browser
- Interacting with pages that require JavaScript
- When user needs to visually see or interact with a page
- Debugging authentication or session issues
- Scraping dynamic content that requires JS execution

---

## Efficiency Guide

### DOM Inspection Over Screenshots

**Don't** take screenshots to see page state. **Do** parse the DOM directly:

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
sleep 0.5 && pnpm --silent --prefix {baseDir} browser eval '...'
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

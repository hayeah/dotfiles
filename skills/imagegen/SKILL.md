---
name: imagegen
description: AI image generation with OpenAI and Gemini providers. Use when the user wants to generate, edit, or remix images from text prompts or reference images.
---

# hayeah.imagegen

## Setup

```bash
cd {baseDir} && uv tool install -e .
```

Requires env vars (in `~/.env.secret`):
- `OPENAI_API_KEY` — for OpenAI
- `GEMINI_API_KEY` — for Gemini

## API

Read `{baseDir}/src/hayeah/imagegen/__init__.py` for full API with docstrings.

## Quick examples

```bash
godotenv -f ~/.env.secret python -c '
from hayeah.imagegen import generate
generate("a cat wearing a top hat")[0].save("cat.png")
'
```

```bash
godotenv -f ~/.env.secret python -c '
from hayeah.imagegen import generate
generate("a landscape", provider="gemini", aspect_ratio="16:9")[0].save("land.png")
'
```

```bash
godotenv -f ~/.env.secret python -c '
from hayeah.imagegen import edit
from pathlib import Path
edit("make it blue", images=[Path("cat.png")])[0].save("cat-blue.png")
'
```

## CLI fallback

```bash
godotenv -f ~/.env.secret imagegen openai create "a cat" -o cat.png
godotenv -f ~/.env.secret imagegen gemini create "a cat" -o cat.png
```

See {baseDir}/CLI.md for full CLI reference.

## When to Use

- User asks to generate, create, or draw an image
- User wants to edit or remix an existing image
- User needs a logo, icon, illustration, or visual asset
- User wants to iterate on an image with multi-turn editing (OpenAI)

## Efficiency Guide

### Pick the Right Provider

- **OpenAI**: Better for iterative editing (multi-turn), streaming previews, and when you need transparent backgrounds. Supports attaching both images and text.
- **Gemini**: Good for quick single-shot generation. Imagen models excel at photorealistic output. Supports aspect ratio control.

### Use Multi-Turn for Iteration

When the user wants to refine an image, use OpenAI's `previous_response_id` rather than regenerating from scratch.

### Attach Context Instead of Describing

When the user has a reference image, pass it as `images=[Path("ref.png")]` rather than trying to describe it in the prompt.

---
name: imagegen
description: AI image generation CLI with OpenAI and Gemini providers. Use when the user wants to generate, edit, or remix images from text prompts or reference images.
---

# imagegen

AI image generation CLI supporting OpenAI (Responses API with streaming) and Google Gemini/Imagen providers.

## Setup

Run once before first use:

```bash
cd {baseDir} && uv tool install -e .
```

Requires API keys in `~/.env.secret`:
- `OPENAI_API_KEY` — for `imagegen openai`
- `GEMINI_API_KEY` — for `imagegen gemini`

## List Available Models

```bash
godotenv -f ~/.env.secret imagegen openai ls
godotenv -f ~/.env.secret imagegen gemini ls
```

Show available models for each provider. Useful for discovering model names before generating.

## OpenAI: Generate Images

```bash
godotenv -f ~/.env.secret imagegen openai create "a cat wearing a hat" -o out.png
godotenv -f ~/.env.secret imagegen openai create "a landscape" -o out.png --size 1536x1024 --quality high
godotenv -f ~/.env.secret imagegen openai create "a logo" -o out.png --background transparent
```

Generate images using OpenAI's Responses API. Streams partial previews during generation.

Options:
- `-o, --output` (required) — output file path
- `-a, --attach` (repeatable) — attach image or text files as context
- `--model` — text model (default: `gpt-5`)
- `--image-model` — image model (e.g. `gpt-image-1.5`, auto-selected if omitted)
- `--size` — `1024x1024`, `1024x1536`, `1536x1024`, `auto` (default: `auto`)
- `--quality` — `low`, `medium`, `high`, `auto` (default: `auto`)
- `--background` — `transparent`, `opaque`, `auto` (default: `auto`)
- `--partial` — number of streaming previews 0-3 (default: `3`)
- `--previous` — response ID for multi-turn editing

Output: prints file path to stdout, response ID to stderr.

## OpenAI: Multi-Turn Editing

```bash
godotenv -f ~/.env.secret imagegen openai create "a cat" -o v1.png
# stderr: response_id: resp_abc123
godotenv -f ~/.env.secret imagegen openai create "make it orange" -o v2.png --previous resp_abc123
```

Chain edits by passing the response ID from a previous generation. Each create prints `response_id: <id>` to stderr.

## Gemini: Generate Images

```bash
godotenv -f ~/.env.secret imagegen gemini create "a cat wearing a hat" -o out.png
godotenv -f ~/.env.secret imagegen gemini create "a landscape" -o out.png --aspect-ratio 16:9 --image-size 2K
godotenv -f ~/.env.secret imagegen gemini create "a photo" -o out.png --model imagen-4.0-generate-001
```

Generate images using Google Gemini or Imagen models. Auto-detects model family and uses the appropriate API.

Options:
- `-o, --output` (required) — output file path
- `-a, --attach` (repeatable) — attach image or text files as context
- `--model` — model name (default: `gemini-2.5-flash-image`)
- `--aspect-ratio` — `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `9:16`, `16:9` (default: `1:1`)
- `--image-size` — `1K`, `2K` (default: `1K`)

## Attachments

```bash
godotenv -f ~/.env.secret imagegen openai create "remix this" -o out.png -a reference.jpg -a notes.txt
godotenv -f ~/.env.secret imagegen gemini create "edit this photo" -o out.png -a photo.jpg
```

Attach reference images or text files with `-a`. Images are sent as visual input; text files are appended to the prompt. Supported image formats: jpg, png, gif, webp, bmp, tiff, svg.

## When to Use

- User asks to generate, create, or draw an image
- User wants to edit or remix an existing image
- User needs a logo, icon, illustration, or visual asset
- User wants to iterate on an image with multi-turn editing (OpenAI)

---

## Efficiency Guide

### Pick the Right Provider

- **OpenAI**: Better for iterative editing (multi-turn), streaming previews, and when you need transparent backgrounds. Supports attaching both images and text.
- **Gemini**: Good for quick single-shot generation. Imagen models excel at photorealistic output. Supports aspect ratio control.

### Use Multi-Turn for Iteration

When the user wants to refine an image, use OpenAI's `--previous` flag rather than regenerating from scratch. Capture the response ID from stderr and pass it to subsequent calls.

### Attach Context Instead of Describing

When the user has a reference image or style notes in a file, attach them with `-a` rather than trying to describe them in the prompt.

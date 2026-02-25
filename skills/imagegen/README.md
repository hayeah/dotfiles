# imagegen

AI image generation CLI with provider-specific subcommands.

## Install

```bash
cd skills/imagegen && uv tool install -e .
```

## Environment

API keys are loaded automatically from `~/.env.secret` if the file exists.

- `OPENAI_API_KEY` — required for `imagegen openai`
- `GEMINI_API_KEY` — required for `imagegen gemini`

## OpenAI

Uses the [Responses API](https://developers.openai.com/api/docs/guides/image-generation) with the `image_generation` tool.

### List models

```bash
imagegen openai ls
```

### Create image

```bash
imagegen openai create "a cat wearing a hat" -o out.png
imagegen openai create "a landscape" -o out.png --size 1536x1024 --quality high
imagegen openai create "a logo" -o out.png --background transparent
imagegen openai create "remix this" -o out.png -a reference.jpg -a notes.txt
```

Options:

- `-o, --output` — output file path (required)
- `-a, --attach` — attach images or text files (repeatable)
- `--model` — text model (default: `gpt-5`)
- `--image-model` — image model (e.g. `gpt-image-1.5`, optional)
- `--size` — `1024x1024`, `1024x1536`, `1536x1024`, `auto` (default: `auto`)
- `--quality` — `low`, `medium`, `high`, `auto` (default: `auto`)
- `--background` — `transparent`, `opaque`, `auto` (default: `auto`)
- `--previous` — path to a previous output image for multi-turn editing

### Multi-turn editing

Each `create` saves a sidecar `{output}.imagegen.json` with the response ID. Use `--previous` to chain:

```bash
imagegen openai create "a cat in a garden" -o v1.png
imagegen openai create "make the cat orange" -o v2.png --previous v1.png
imagegen openai create "add a butterfly" -o v3.png --previous v2.png
```

## Gemini

Uses the [google-genai SDK](https://ai.google.dev/gemini-api/docs/image-generation). Auto-detects model family:

- **Gemini native** models (e.g. `gemini-2.5-flash-image`) use `generate_content`
- **Imagen** models (e.g. `imagen-4.0-generate-001`) use `generate_images`

### List models

```bash
imagegen gemini ls
```

### Create image

```bash
imagegen gemini create "a cat wearing a hat" -o out.png
imagegen gemini create "a landscape" -o out.png --aspect-ratio 16:9 --image-size 2K
imagegen gemini create "remix this" -o out.png -a reference.jpg
imagegen gemini create "a photo" -o out.png --model imagen-4.0-generate-001
```

Options:

- `-o, --output` — output file path (required)
- `-a, --attach` — attach images or text files (repeatable)
- `--model` — model (default: `gemini-2.5-flash-image`)
- `--aspect-ratio` — `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `9:16`, `16:9` (default: `1:1`)
- `--image-size` — `1K`, `2K` (default: `1K`)

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

### List models

```bash
imagegen openai ls
```

### Create

Uses the [Responses API](https://developers.openai.com/api/docs/guides/image-generation) with the `image_generation` tool. Supports multi-turn editing and attachments.

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
- `--previous` — response ID from a previous `create` for multi-turn editing
- `--partial` — number of partial image previews during streaming, 0-3 (default: `3`)

### Streaming partial images

By default, `create` streams 3 partial image previews to the output path while the final image is being generated. This provides faster visual feedback. The final full-quality image overwrites the partials on completion.

```bash
# Default: 3 partial previews
imagegen openai create "a river of owl feathers" -o out.png

# Fewer partials for faster completion
imagegen openai create "a river of owl feathers" -o out.png --partial 1

# Disable partial previews
imagegen openai create "a river of owl feathers" -o out.png --partial 0
```

### Multi-turn editing

Each `create` prints the response ID to stderr. Use `--previous` with a response ID to chain edits:

```bash
imagegen openai create "a cat in a garden" -o v1.png
# stderr: response_id: resp_abc123
imagegen openai create "make the cat orange" -o v2.png --previous resp_abc123
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

# hayeah.imagegen

Image generation library with OpenAI and Gemini providers.

## Install

```bash
cd skills/imagegen && uv tool install -e .
```

## Environment

API keys loaded from env vars (use `godotenv -f ~/.env.secret`):

- `OPENAI_API_KEY` — for OpenAI provider
- `GEMINI_API_KEY` — for Gemini provider

## Usage

```python
from hayeah.imagegen import generate, edit

# Generate with OpenAI (default)
results = generate("a cat wearing a top hat")
results[0].save("cat.png")

# Generate with Gemini
results = generate("a landscape", provider="gemini", aspect_ratio="16:9")

# Edit an existing image
results = edit("make the hat blue", images=[Path("cat.png")])
results[0].save("cat-blue.png")

# Multi-turn editing (OpenAI)
r1 = generate("a cat in a garden")
r2 = generate("make it orange", previous_response_id=r1[0].metadata["response_id"])

# Streaming partial previews
def on_preview(index, data):
    Path(f"preview-{index}.png").write_bytes(data)

results = generate("a river of owl feathers", on_partial=on_preview)
```

## Ad-hoc usage (python -c)

```bash
godotenv -f ~/.env.secret python -c '
from hayeah.imagegen import generate
generate("a cat wearing a top hat")[0].save("cat.png")
'
```

## API Reference

See `src/hayeah/imagegen/__init__.py` for full type signatures and docstrings.

## CLI

See [CLI.md](CLI.md) for the command-line interface.

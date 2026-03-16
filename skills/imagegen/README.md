# hayeah.imagegen

Image generation library with separate OpenAI and Gemini modules.

## Install

```bash
cd skills/imagegen && uv tool install -e .
```

## Environment

API keys loaded from env vars (use `godotenv -f ~/.env.secret`):

- `OPENAI_API_KEY` — for OpenAI
- `GEMINI_API_KEY` — for Gemini

## Usage

### OpenAI

```python
from hayeah.imagegen.openai import OpenAIProvider

p = OpenAIProvider()

# Responses API (streaming, multi-turn, attachments)
results = p.generate("a cat wearing a top hat")
results[0].save("cat.png")

# With options
results = p.generate("a logo", size="1024x1024", quality="high", background="transparent")

# Multi-turn editing
r1 = p.generate("a cat in a garden")
r2 = p.generate("make it orange", previous_response_id=r1[0].metadata["response_id"])

# Streaming partial previews
def on_preview(index, data):
    Path(f"preview-{index}.png").write_bytes(data)

results = p.generate("a river", on_partial=on_preview)

# Images API (direct, no text model — faster for simple prompts)
p_direct = OpenAIProvider(model=None)
results = p_direct.generate("a simple icon", n=3)

# Edit an existing image
p_direct.edit("make the hat blue", images=[Path("cat.png").read_bytes()])[0].save("cat-blue.png")
```

### Gemini

```python
from hayeah.imagegen.gemini import GeminiProvider

p = GeminiProvider()

# Gemini native model
results = p.generate("a landscape", aspect_ratio="16:9", image_size="2K")
results[0].save("landscape.png")

# Imagen model
p_imagen = GeminiProvider(model="imagen-4.0-generate-001")
results = p_imagen.generate("a photo", n=2)

# With reference image
results = p.generate("remix this", images=[Path("ref.png").read_bytes()])
```

## Ad-hoc usage (python -c)

```bash
godotenv -f ~/.env.secret python -c '
from hayeah.imagegen.openai import OpenAIProvider
OpenAIProvider().generate("a cat wearing a top hat")[0].save("cat.png")
'
```

## API Reference

- OpenAI: `src/hayeah/imagegen/openai.py`
- Gemini: `src/hayeah/imagegen/gemini.py`
- Shared types: `src/hayeah/imagegen/__init__.py`

## CLI

See [CLI.md](CLI.md) for the command-line interface.

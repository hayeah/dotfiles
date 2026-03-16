# hayeah.imagegen

Image generation with OpenAI and Gemini providers.

OpenAI usage:

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

Gemini usage:

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

Both providers return list[ImageResult].

## hayeah.imagegen.output_format_from_path

```python
def output_format_from_path(path: Path | str | None) -> str
```

Infer output format from a file path extension.

## hayeah.imagegen.ImageResult

A single generated image.

**Attributes:**
- `data` — Raw image bytes (PNG, JPEG, or WebP).
- `format` — Image format — "png", "jpeg", or "webp".
- `metadata` — Provider-specific info. OpenAI: {"response_id": str, "model": str, ...} Gemini: {"model": str}

### ImageResult#save

```python
def save(path: Path | str) -> Path
```

Write image to disk. Creates parent dirs. Returns the path.

# hayeah.imagegen.openai

OpenAI image generation.

Two APIs available, auto-selected by whether model is set:
- Responses API (streaming, multi-turn, attachments) — model="gpt-5"
- Images API (direct, no text model) — model=None

Quick start:
```python
from hayeah.imagegen.openai import OpenAIProvider
p = OpenAIProvider()
p.generate("a cat wearing a top hat")[0].save("cat.png")
```

Edit:
```python
p = OpenAIProvider(model=None)
p.edit("make it blue", images=[Path("cat.png").read_bytes()])[0].save("blue.png")
```

## hayeah.imagegen.openai.OpenAIProvider

OpenAI image generation via Responses API or Images API.

Auto-selects Responses API (streaming, multi-turn) vs Images API
(direct, no text model) based on whether model is set.

**Args:**
- `model` — Text model for Responses API (default: "gpt-5"). Set to None to use Images API directly.
- `image_model` — Underlying image model (default: "gpt-image-1.5").
- `client` — Inject an OpenAI client. Created automatically if None.

### OpenAIProvider#constructor

```python
def __init__(
    *,
    model: str | None = 'gpt-5',
    image_model: str = 'gpt-image-1.5',
    client: OpenAI | None = None,
)
```

### OpenAIProvider#client (property)

### OpenAIProvider#generate

```python
def generate(
    prompt: str,
    *,
    images: list[bytes] | None = None,
    image_attachments: list[Attachment] | None = None,
    n: int = 1,
    size: str = 'auto',
    quality: str = 'auto',
    background: str = 'auto',
    output_format: str = 'png',
    previous_response_id: str | None = None,
    on_partial: Callable[[int, bytes], None] | None = None,
    partial_images: int = 3,
) -> list[ImageResult]
```

Generate images from a text prompt.

When self.model is set, uses the Responses API (supports streaming,
multi-turn, attachments). When self.model is None, calls the Images
API directly.

**Args:**
- `prompt` — Text description of the image.
- `images` — Reference images as raw bytes.
- `image_attachments` — Reference images as Attachment objects (alternative to images, used by CLI).
- `n` — Number of images (Images API only).
- `size` — "auto", "1024x1024", "1536x1024", "1024x1536".
- `quality` — "auto", "low", "medium", "high".
- `background` — "auto", "transparent", "opaque".
- `output_format` — "png", "jpeg", or "webp".
- `previous_response_id` — Chain edits with a prior response (Responses API only).
- `on_partial` — Callback receiving (index, image_bytes) for streaming partial previews (Responses API only).
- `partial_images` — Number of partial previews, 0-3 (Responses API only).


**Returns:**
List of ImageResult.

### OpenAIProvider#edit

```python
def edit(
    prompt: str,
    *,
    images: list[bytes],
    n: int = 1,
    size: str = 'auto',
    quality: str = 'auto',
    output_format: str = 'png',
) -> list[ImageResult]
```

Edit images using the Images edit endpoint.

**Args:**
- `prompt` — Text description of the edits.
- `images` — Source images as raw bytes. At least one required.
- `n` — Number of variations.
- `size` — "auto", "1024x1024", "1536x1024", "1024x1536".
- `quality` — "auto", "low", "medium", "high".
- `output_format` — "png", "jpeg", or "webp".


**Returns:**
List of ImageResult.

# hayeah.imagegen.gemini

Google Gemini/Imagen image generation.

Auto-detects model family:
- Gemini native models (e.g. "gemini-2.5-flash-image") use generate_content.
- Imagen models (e.g. "imagen-4.0-generate-001") use generate_images.

Quick start:
```python
from hayeah.imagegen.gemini import GeminiProvider
p = GeminiProvider()
p.generate("a cat wearing a top hat")[0].save("cat.png")
```

## hayeah.imagegen.gemini.GeminiProvider

Google Gemini/Imagen image generation.

Auto-detects model family:
- Gemini native models (e.g. "gemini-2.5-flash-image") use generate_content.
- Imagen models (e.g. "imagen-4.0-generate-001") use generate_images.

**Args:**
- `model` — Model name (default: "gemini-2.5-flash-image").
- `client` — Inject a genai.Client. Created automatically if None.

### GeminiProvider#constructor

```python
def __init__(
    *,
    model: str = 'gemini-2.5-flash-image',
    client: genai.Client | None = None,
)
```

### GeminiProvider#client (property)

### GeminiProvider#generate

```python
def generate(
    prompt: str,
    *,
    images: list[bytes] | None = None,
    n: int = 1,
    aspect_ratio: str = '1:1',
    image_size: str = '1K',
) -> list[ImageResult]
```

Generate images from a text prompt.

**Args:**
- `prompt` — Text description of the image.
- `images` — Reference images as raw bytes.
- `n` — Number of images to generate (max 4).
- `aspect_ratio` — "1:1", "16:9", "9:16", etc.
- `image_size` — "1K" or "2K".

### GeminiProvider#list_models

```python
def list_models() -> list[str]
```

List available image generation models.

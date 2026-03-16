"""Tests for Gemini provider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from .gemini import GeminiProvider, is_image_model, is_imagen_model


def test_is_image_model() -> None:
    assert is_image_model("models/gemini-2.5-flash-image") is True
    assert is_image_model("models/gemini-3-pro-image-preview") is True
    assert is_image_model("models/imagen-4.0-generate-001") is True
    assert is_image_model("models/gemini-2.5-flash") is False
    assert is_image_model("models/gemini-2.5-pro") is False


def test_is_imagen_model() -> None:
    assert is_imagen_model("imagen-4.0-generate-001") is True
    assert is_imagen_model("imagen-4.0-ultra-generate-001") is True
    assert is_imagen_model("gemini-2.5-flash-image") is False


def test_gemini_native_generate() -> None:
    image_bytes = b"PNG-gemini-output"

    mock_inline_data = MagicMock()
    mock_inline_data.data = image_bytes

    mock_part = MagicMock()
    mock_part.inline_data = mock_inline_data

    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(model="gemini-2.5-flash-image", client=mock_client)
    results = provider.generate("test")

    assert len(results) == 1
    assert results[0].data == image_bytes
    assert results[0].format == "png"
    assert results[0].metadata["model"] == "gemini-2.5-flash-image"
    mock_client.models.generate_content.assert_called_once()


def test_imagen_generate() -> None:
    image_bytes = b"PNG-imagen-output"

    mock_image = MagicMock()
    mock_image.image_bytes = image_bytes

    mock_generated = MagicMock()
    mock_generated.image = mock_image

    mock_response = MagicMock()
    mock_response.generated_images = [mock_generated]

    mock_client = MagicMock()
    mock_client.models.generate_images.return_value = mock_response

    provider = GeminiProvider(model="imagen-4.0-generate-001", client=mock_client)
    results = provider.generate("test")

    assert len(results) == 1
    assert results[0].data == image_bytes
    mock_client.models.generate_images.assert_called_once()

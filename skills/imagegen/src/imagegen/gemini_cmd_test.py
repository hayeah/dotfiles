"""Tests for Gemini provider module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from .gemini_cmd import GeminiGenerator, _is_image_model, _is_imagen_model


def test_is_image_model() -> None:
    assert _is_image_model("models/gemini-2.5-flash-image") is True
    assert _is_image_model("models/gemini-3-pro-image-preview") is True
    assert _is_image_model("models/imagen-4.0-generate-001") is True
    assert _is_image_model("models/gemini-2.5-flash") is False
    assert _is_image_model("models/gemini-2.5-pro") is False


def test_is_imagen_model() -> None:
    assert _is_imagen_model("imagen-4.0-generate-001") is True
    assert _is_imagen_model("imagen-4.0-ultra-generate-001") is True
    assert _is_imagen_model("gemini-2.5-flash-image") is False


def test_gemini_native_run(tmp_path: Path) -> None:
    image_bytes = b"PNG-gemini-output"

    mock_inline_data = MagicMock()
    mock_inline_data.data = image_bytes

    mock_part = MagicMock()
    mock_part.inline_data = mock_inline_data

    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    output_path = tmp_path / "result.png"
    gen = GeminiGenerator(
        prompt="test",
        output_path=output_path,
        model="gemini-2.5-flash-image",
    )

    with patch("imagegen.gemini_cmd.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        result = gen.run()

    assert result == output_path
    assert output_path.read_bytes() == image_bytes
    mock_client.models.generate_content.assert_called_once()


def test_imagen_run(tmp_path: Path) -> None:
    image_bytes = b"PNG-imagen-output"

    mock_image = MagicMock()
    mock_image.image_bytes = image_bytes

    mock_generated = MagicMock()
    mock_generated.image = mock_image

    mock_response = MagicMock()
    mock_response.generated_images = [mock_generated]

    output_path = tmp_path / "result.png"
    gen = GeminiGenerator(
        prompt="test",
        output_path=output_path,
        model="imagen-4.0-generate-001",
    )

    with patch("imagegen.gemini_cmd.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        result = gen.run()

    assert result == output_path
    assert output_path.read_bytes() == image_bytes
    mock_client.models.generate_images.assert_called_once()

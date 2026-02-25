"""Tests for OpenAI provider module."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from .attachments import Attachment
from .openai_cmd import OpenAIGenerator, _load_previous_response_id


def test_build_content_text_only() -> None:
    gen = OpenAIGenerator(prompt="a red circle", output_path=Path("/tmp/out.png"))
    content = gen._build_content()

    assert len(content) == 1
    assert content[0] == {"type": "input_text", "text": "a red circle"}


def test_build_content_with_image_attachments() -> None:
    att = Attachment(path=Path("ref.png"), is_image=True, data="AAAA")
    gen = OpenAIGenerator(
        prompt="remix this",
        output_path=Path("/tmp/out.png"),
        image_attachments=[att],
    )
    content = gen._build_content()

    assert len(content) == 2
    assert content[0] == {"type": "input_text", "text": "remix this"}
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")


def test_build_request_defaults() -> None:
    gen = OpenAIGenerator(prompt="test", output_path=Path("/tmp/out.png"))
    req = gen._build_request()

    assert req["model"] == "gpt-5"
    tool = req["tools"][0]
    assert tool["type"] == "image_generation"
    assert "model" not in tool  # no image_model by default
    assert "previous_response_id" not in req


def test_build_request_with_image_model() -> None:
    gen = OpenAIGenerator(
        prompt="test",
        output_path=Path("/tmp/out.png"),
        model="gpt-4.1",
        image_model="gpt-image-1.5",
        size="1024x1024",
        quality="high",
        background="transparent",
    )
    req = gen._build_request()

    assert req["model"] == "gpt-4.1"
    tool = req["tools"][0]
    assert tool["model"] == "gpt-image-1.5"
    assert tool["size"] == "1024x1024"
    assert tool["quality"] == "high"
    assert tool["background"] == "transparent"


def test_build_request_with_previous() -> None:
    gen = OpenAIGenerator(
        prompt="make it blue",
        output_path=Path("/tmp/out.png"),
        previous_response_id="resp_abc123",
    )
    req = gen._build_request()

    assert req["previous_response_id"] == "resp_abc123"


def test_extract_image() -> None:
    image_bytes = b"fake-image-data"
    encoded = base64.b64encode(image_bytes).decode("ascii")

    mock_output = MagicMock()
    mock_output.type = "image_generation_call"
    mock_output.result = encoded

    mock_response = MagicMock()
    mock_response.output = [mock_output]

    gen = OpenAIGenerator(prompt="test", output_path=Path("/tmp/out.png"))
    result = gen._extract_image(mock_response)

    assert result == image_bytes


def test_run_saves_image_and_sidecar(tmp_path: Path) -> None:
    image_bytes = b"PNG-image-content"
    encoded = base64.b64encode(image_bytes).decode("ascii")

    mock_output = MagicMock()
    mock_output.type = "image_generation_call"
    mock_output.result = encoded

    mock_response = MagicMock()
    mock_response.output = [mock_output]
    mock_response.id = "resp_test123"

    output_path = tmp_path / "result.png"
    gen = OpenAIGenerator(prompt="test", output_path=output_path)

    with patch("imagegen.openai_cmd.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        result = gen.run()

    assert result == output_path
    assert output_path.read_bytes() == image_bytes

    sidecar = Path(str(output_path) + ".imagegen.json")
    assert sidecar.exists()
    meta = json.loads(sidecar.read_text())
    assert meta["response_id"] == "resp_test123"
    assert meta["model"] == "gpt-5"
    assert "image_model" not in meta


def test_sidecar_includes_image_model(tmp_path: Path) -> None:
    encoded = base64.b64encode(b"img").decode("ascii")

    mock_output = MagicMock()
    mock_output.type = "image_generation_call"
    mock_output.result = encoded

    mock_response = MagicMock()
    mock_response.output = [mock_output]
    mock_response.id = "resp_456"

    output_path = tmp_path / "result.png"
    gen = OpenAIGenerator(prompt="test", output_path=output_path, image_model="gpt-image-1.5")

    with patch("imagegen.openai_cmd.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client
        gen.run()

    sidecar = Path(str(output_path) + ".imagegen.json")
    meta = json.loads(sidecar.read_text())
    assert meta["image_model"] == "gpt-image-1.5"


def test_load_previous_response_id(tmp_path: Path) -> None:
    img = tmp_path / "prev.png"
    img.write_bytes(b"fake")
    sidecar = tmp_path / "prev.png.imagegen.json"
    sidecar.write_text(json.dumps({"response_id": "resp_xyz", "model": "gpt-5"}))

    assert _load_previous_response_id(img) == "resp_xyz"


def test_load_previous_response_id_missing(tmp_path: Path) -> None:
    img = tmp_path / "no_sidecar.png"
    img.write_bytes(b"fake")

    try:
        _load_previous_response_id(img)
        assert False, "Should have raised"
    except Exception as e:
        assert "No sidecar metadata" in str(e)

"""Tests for OpenAI provider module."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

from .attachments import Attachment
from .openai_cmd import OpenAIResponses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_partial_event(index: int, image_bytes: bytes) -> MagicMock:
    ev = MagicMock()
    ev.type = "response.image_generation_call.partial_image"
    ev.partial_image_index = index
    ev.partial_image_b64 = base64.b64encode(image_bytes).decode()
    return ev


def _make_completed_event(response: MagicMock) -> MagicMock:
    ev = MagicMock()
    ev.type = "response.completed"
    ev.response = response
    return ev


def _make_response(image_bytes: bytes, response_id: str = "resp_123") -> MagicMock:
    """Build a mock Response with a single image_generation_call output."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    mock_output = MagicMock()
    mock_output.type = "image_generation_call"
    mock_output.result = encoded
    mock_response = MagicMock()
    mock_response.output = [mock_output]
    mock_response.id = response_id
    return mock_response


def _mock_stream(events: list[MagicMock]) -> MagicMock:
    """Create a mock context manager that yields events."""
    stream = MagicMock()
    stream.__enter__ = MagicMock(return_value=iter(events))
    stream.__exit__ = MagicMock(return_value=False)
    return stream


# ---------------------------------------------------------------------------
# _build_content / _build_request
# ---------------------------------------------------------------------------


def test_build_content_text_only() -> None:
    gen = OpenAIResponses(prompt="a red circle", output_path=Path("/tmp/out.png"))
    content = gen._build_content()

    assert len(content) == 1
    assert content[0] == {"type": "input_text", "text": "a red circle"}


def test_build_content_with_image_attachments() -> None:
    att = Attachment(path=Path("ref.png"), is_image=True, data="AAAA")
    gen = OpenAIResponses(
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
    gen = OpenAIResponses(prompt="test", output_path=Path("/tmp/out.png"))
    req = gen._build_request()

    assert req["model"] == "gpt-5"
    tool = req["tools"][0]
    assert tool["type"] == "image_generation"
    assert "model" not in tool
    assert "previous_response_id" not in req
    assert tool["partial_images"] == 3


def test_build_request_no_partial_when_zero() -> None:
    gen = OpenAIResponses(prompt="test", output_path=Path("/tmp/out.png"), partial_images=0)
    req = gen._build_request()
    tool = req["tools"][0]
    assert "partial_images" not in tool


def test_build_request_with_image_model() -> None:
    gen = OpenAIResponses(
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
    gen = OpenAIResponses(
        prompt="make it blue",
        output_path=Path("/tmp/out.png"),
        previous_response_id="resp_abc123",
    )
    req = gen._build_request()

    assert req["previous_response_id"] == "resp_abc123"


# ---------------------------------------------------------------------------
# _extract_image
# ---------------------------------------------------------------------------


def test_extract_image() -> None:
    image_bytes = b"fake-image-data"
    mock_response = _make_response(image_bytes)
    gen = OpenAIResponses(prompt="test", output_path=Path("/tmp/out.png"))
    result = gen._extract_image(mock_response)
    assert result == image_bytes


# ---------------------------------------------------------------------------
# run (streaming via Responses API)
# ---------------------------------------------------------------------------


def test_run_with_partials(tmp_path: Path) -> None:
    final_bytes = b"final-hq-image"
    response = _make_response(final_bytes, "resp_abc")

    events = [
        _make_partial_event(0, b"partial-0"),
        _make_partial_event(1, b"partial-1"),
        _make_completed_event(response),
    ]

    output_path = tmp_path / "out.png"
    gen = OpenAIResponses(prompt="test", output_path=output_path, partial_images=2)

    with patch("imagegen.openai_cmd.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.responses.stream.return_value = _mock_stream(events)
        mock_cls.return_value = mock_client

        result_path, response_id = gen.run()

    assert result_path == output_path
    assert response_id == "resp_abc"
    assert output_path.read_bytes() == final_bytes


def test_run_no_partials(tmp_path: Path) -> None:
    """partial_images=0 still works — just no partial events."""
    final_bytes = b"final-image"
    response = _make_response(final_bytes, "resp_nop")

    events = [_make_completed_event(response)]

    output_path = tmp_path / "out.png"
    gen = OpenAIResponses(prompt="test", output_path=output_path, partial_images=0)

    with patch("imagegen.openai_cmd.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.responses.stream.return_value = _mock_stream(events)
        mock_cls.return_value = mock_client

        result_path, response_id = gen.run()

    assert result_path == output_path
    assert response_id == "resp_nop"
    assert output_path.read_bytes() == final_bytes


def test_run_with_previous(tmp_path: Path) -> None:
    """--previous passes previous_response_id to the request."""
    final_bytes = b"edited"
    response = _make_response(final_bytes, "resp_edit")
    events = [_make_completed_event(response)]

    output_path = tmp_path / "out.png"
    gen = OpenAIResponses(
        prompt="make it blue",
        output_path=output_path,
        previous_response_id="resp_prev",
    )

    with patch("imagegen.openai_cmd.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.responses.stream.return_value = _mock_stream(events)
        mock_cls.return_value = mock_client

        _, response_id = gen.run()

    assert response_id == "resp_edit"
    call_kwargs = mock_client.responses.stream.call_args[1]
    assert call_kwargs["previous_response_id"] == "resp_prev"

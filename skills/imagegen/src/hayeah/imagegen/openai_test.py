"""Tests for OpenAI provider."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

from . import ImageResult
from .attachments import Attachment
from .openai import OpenAIProvider


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
    mock_response.model_dump.return_value = {
        "output": [{"type": "image_generation_call", "result": encoded}],
        "input": [],
    }
    return mock_response


def _mock_stream(events: list[MagicMock]) -> MagicMock:
    """Create a mock context manager that yields events."""
    stream = MagicMock()
    stream.__enter__ = MagicMock(return_value=iter(events))
    stream.__exit__ = MagicMock(return_value=False)
    return stream


# ---------------------------------------------------------------------------
# Responses API (generate with text model)
# ---------------------------------------------------------------------------


def test_generate_responses_api() -> None:
    final_bytes = b"final-hq-image"
    response = _make_response(final_bytes, "resp_abc")
    events = [
        _make_partial_event(0, b"partial-0"),
        _make_completed_event(response),
    ]

    mock_client = MagicMock()
    mock_client.responses.stream.return_value = _mock_stream(events)

    provider = OpenAIProvider(model="gpt-5", client=mock_client)
    partials_received: list[tuple[int, bytes]] = []

    results = provider.generate(
        "test",
        on_partial=lambda i, d: partials_received.append((i, d)),
        partial_images=1,
    )

    assert len(results) == 1
    assert results[0].data == final_bytes
    assert results[0].format == "png"
    assert "response_id" in results[0].metadata
    assert len(partials_received) == 1


def test_generate_responses_with_previous() -> None:
    final_bytes = b"edited"
    response = _make_response(final_bytes, "resp_edit")
    events = [_make_completed_event(response)]

    mock_client = MagicMock()
    mock_client.responses.stream.return_value = _mock_stream(events)

    provider = OpenAIProvider(model="gpt-5", client=mock_client)
    results = provider.generate(
        "make it blue",
        previous_response_id="resp_prev",
        partial_images=0,
    )

    assert len(results) == 1
    call_kwargs = mock_client.responses.stream.call_args[1]
    assert call_kwargs["previous_response_id"] == "resp_prev"


# ---------------------------------------------------------------------------
# Images API (generate without text model)
# ---------------------------------------------------------------------------


def test_generate_images_api() -> None:
    image_bytes = b"direct-image"
    encoded = base64.b64encode(image_bytes).decode()

    mock_image = MagicMock()
    mock_image.b64_json = encoded

    mock_result = MagicMock()
    mock_result.data = [mock_image]

    mock_client = MagicMock()
    mock_client.images.generate.return_value = mock_result

    provider = OpenAIProvider(model=None, client=mock_client)
    results = provider.generate("test")

    assert len(results) == 1
    assert results[0].data == image_bytes


# ---------------------------------------------------------------------------
# ImageResult.save
# ---------------------------------------------------------------------------


def test_image_result_save(tmp_path: Path) -> None:
    result = ImageResult(data=b"png-bytes", format="png", metadata={})
    path = result.save(tmp_path / "sub" / "out.png")

    assert path.exists()
    assert path.read_bytes() == b"png-bytes"

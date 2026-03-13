"""Tests for fzfmatch using language-agnostic JSON test vectors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hayeah.fzfmatch import (
    MatchError,
    contains_word_exact,
    contains_word_prefix,
    parse_matcher,
)

TESTDATA = json.loads(
    (Path(__file__).parent / "fzfmatch_testdata.json").read_text()
)

SAMPLE_PATHS = TESTDATA["sample_paths"]


# ---------------------------------------------------------------------------
# Term-level matching
# ---------------------------------------------------------------------------

class TestTermMatch:
    @pytest.mark.parametrize(
        "tc",
        TESTDATA["term_match_tests"],
        ids=[tc["name"] for tc in TESTDATA["term_match_tests"]],
    )
    def test_term_match(self, tc: dict):
        m = parse_matcher(tc["pattern"])
        got = m.match(SAMPLE_PATHS)
        assert got == tc["expected"]


# ---------------------------------------------------------------------------
# Parse errors
# ---------------------------------------------------------------------------

class TestParseErrors:
    @pytest.mark.parametrize(
        "tc",
        TESTDATA["parse_error_tests"],
        ids=[tc["name"] for tc in TESTDATA["parse_error_tests"]],
    )
    def test_parse_error(self, tc: dict):
        with pytest.raises(MatchError):
            parse_matcher(tc["pattern"])


# ---------------------------------------------------------------------------
# Expression-level (compound / union)
# ---------------------------------------------------------------------------

class TestExpression:
    @pytest.mark.parametrize(
        "tc",
        TESTDATA["expression_tests"],
        ids=[tc["name"] for tc in TESTDATA["expression_tests"]],
    )
    def test_expression(self, tc: dict):
        m = parse_matcher(tc["pattern"])
        got = m.match(tc["paths"])
        assert sorted(got) == tc["expected_sorted"]


# ---------------------------------------------------------------------------
# Word-boundary helpers
# ---------------------------------------------------------------------------

class TestWordBoundary:
    @pytest.mark.parametrize(
        "tc",
        TESTDATA["word_boundary_tests"],
        ids=[tc["name"] for tc in TESTDATA["word_boundary_tests"]],
    )
    def test_word_exact(self, tc: dict):
        assert contains_word_exact(tc["s"], tc["needle"]) == tc["word_exact"]

    @pytest.mark.parametrize(
        "tc",
        TESTDATA["word_boundary_tests"],
        ids=[tc["name"] for tc in TESTDATA["word_boundary_tests"]],
    )
    def test_word_prefix(self, tc: dict):
        assert contains_word_prefix(tc["s"], tc["needle"]) == tc["word_prefix"]

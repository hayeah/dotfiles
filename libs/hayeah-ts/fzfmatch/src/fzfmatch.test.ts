import { describe, it, expect } from "vitest";
import {
  MatchError,
  containsWordExact,
  containsWordPrefix,
  parseMatcher,
} from "./fzfmatch.js";
import testdata from "./fzfmatch_testdata.json";

const SAMPLE_PATHS: string[] = testdata.sample_paths;

// ---------------------------------------------------------------------------
// Term-level matching
// ---------------------------------------------------------------------------

describe("term match", () => {
  for (const tc of testdata.term_match_tests) {
    it(tc.name, () => {
      const m = parseMatcher(tc.pattern);
      const got = m.match(SAMPLE_PATHS);
      expect(got).toEqual(tc.expected);
    });
  }
});

// ---------------------------------------------------------------------------
// Parse errors
// ---------------------------------------------------------------------------

describe("parse errors", () => {
  for (const tc of testdata.parse_error_tests) {
    it(tc.name, () => {
      expect(() => parseMatcher(tc.pattern)).toThrow(MatchError);
    });
  }
});

// ---------------------------------------------------------------------------
// Expression-level (compound / union)
// ---------------------------------------------------------------------------

describe("expression", () => {
  for (const tc of testdata.expression_tests) {
    it(tc.name, () => {
      const m = parseMatcher(tc.pattern);
      const got = m.match(tc.paths);
      expect([...got].sort()).toEqual(tc.expected_sorted);
    });
  }
});

// ---------------------------------------------------------------------------
// Word-boundary helpers
// ---------------------------------------------------------------------------

describe("word boundary", () => {
  describe("containsWordExact", () => {
    for (const tc of testdata.word_boundary_tests) {
      it(tc.name, () => {
        expect(containsWordExact(tc.s, tc.needle)).toBe(tc.word_exact);
      });
    }
  });

  describe("containsWordPrefix", () => {
    for (const tc of testdata.word_boundary_tests) {
      it(tc.name, () => {
        expect(containsWordPrefix(tc.s, tc.needle)).toBe(tc.word_prefix);
      });
    }
  });
});

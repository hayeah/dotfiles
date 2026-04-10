import { describe, it, expect } from "vitest";
import {
  generate,
  resolve,
  ID_ALPHABET,
  IDTooShortError,
  AmbiguousIDError,
  IDNotFoundError,
} from "./index.js";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const testdata = JSON.parse(
  readFileSync(join(__dirname, "../../../testdata/shortid.json"), "utf-8"),
);

describe("generate", () => {
  it("produces IDs from the correct alphabet", () => {
    const id = generate(new Set());
    expect(id.length).toBeGreaterThanOrEqual(testdata.min_length);
    expect(id.length).toBeLessThanOrEqual(testdata.max_length);
    for (const ch of id) {
      expect(testdata.alphabet).toContain(ch);
    }
  });

  it("does not collide with existing", () => {
    const existing = new Set(["a3f", "b7k"]);
    const id = generate(existing);
    expect(existing.has(id)).toBe(false);
  });

  it("generates unique IDs over many calls", () => {
    const seen = new Set<string>();
    for (let i = 0; i < 100; i++) {
      const id = generate(seen);
      expect(seen.has(id)).toBe(false);
      seen.add(id);
    }
  });
});

describe("resolve", () => {
  for (const tc of testdata.resolve_tests) {
    it(tc.name, () => {
      const result = resolve(tc.query, tc.candidates);
      expect(result).toBe(tc.expected);
    });
  }
});

describe("resolve errors", () => {
  const errorMap: Record<string, new (...args: any[]) => Error> = {
    IDTooShortError,
    AmbiguousIDError,
    IDNotFoundError,
  };

  for (const tc of testdata.resolve_error_tests) {
    it(tc.name, () => {
      const ErrorClass = errorMap[tc.error];
      expect(() => resolve(tc.query, tc.candidates)).toThrow(ErrorClass);
    });
  }
});

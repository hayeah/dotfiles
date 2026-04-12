import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

import { expandEnv } from "./expand_env.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(__dirname, "../../../testdata/expand_env.json");

interface ExpandEnvCase {
  name: string;
  input: string;
  env?: Record<string, string>;
  expected: string;
}

const cases: ExpandEnvCase[] = JSON.parse(readFileSync(fixturePath, "utf-8")).expand_env_tests;

describe("expandEnv", () => {
  let savedEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    savedEnv = { ...process.env };
  });

  afterEach(() => {
    // Wipe everything we may have set, then restore.
    for (const k of Object.keys(process.env)) delete process.env[k];
    Object.assign(process.env, savedEnv);
  });

  for (const tc of cases) {
    it(tc.name, () => {
      const env = tc.env ?? {};
      // Make sure each case starts with the listed vars unset, then set them.
      for (const k of Object.keys(env)) delete process.env[k];
      for (const [k, v] of Object.entries(env)) process.env[k] = v;

      expect(expandEnv(tc.input)).toBe(tc.expected);
    });
  }
});

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { load } from "./index.js";
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { tmpdir } from "os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const testdata = JSON.parse(
  readFileSync(join(__dirname, "../../../testdata/single-envar-config.json"), "utf-8"),
);

const ENV_VAR = "HAYEAH_TEST_CONFIG";
const TMP_DIR = join(tmpdir(), "hayeah-config-test");

beforeEach(() => {
  mkdirSync(TMP_DIR, { recursive: true });
  delete process.env[ENV_VAR];
});

afterEach(() => {
  delete process.env[ENV_VAR];
  rmSync(TMP_DIR, { recursive: true, force: true });
});

describe("config load", () => {
  for (const tc of testdata.load_tests) {
    it(tc.name, () => {
      if (tc.env_value === null || tc.env_value === undefined) {
        delete process.env[ENV_VAR];
      } else if (tc.file_contents !== undefined) {
        // Write a temp file and point the env var at it
        const ext = tc.env_value.endsWith(".toml") ? ".toml" : ".json";
        const filePath = join(TMP_DIR, `config${ext}`);
        writeFileSync(filePath, tc.file_contents);
        process.env[ENV_VAR] = filePath;
      } else if (tc.env_value.startsWith("/nonexistent/")) {
        // Missing file path — use as-is
        process.env[ENV_VAR] = tc.env_value;
      } else {
        process.env[ENV_VAR] = tc.env_value;
      }

      const result = load(ENV_VAR);
      expect(result).toEqual(tc.expected);
    });
  }
});

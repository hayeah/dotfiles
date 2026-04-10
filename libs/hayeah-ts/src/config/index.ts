/**
 * hayeah-ts/config — single-envar config loading.
 *
 * One env var per app (`<APP>_CONFIG`). Value is either a file path
 * (`.json` / `.toml`, detected by extension) or a JSON literal.
 */

import { readFileSync, existsSync } from "fs";

/**
 * Load config from the env var `envVar`.
 *
 * The value is interpreted as:
 * - File path ending `.toml` -> load as TOML (requires `@iarna/toml` or similar — falls back to error)
 * - File path ending `.json` -> load as JSON
 * - Anything else -> parse as JSON literal
 *
 * Returns an empty object when the env var is unset or empty, or when
 * a file path doesn't exist.
 */
export function load(envVar: string): Record<string, unknown> {
  const value = process.env[envVar];
  if (!value) return {};

  if (value.endsWith(".toml")) {
    if (!existsSync(value)) return {};
    // Inline minimal TOML parser for simple key = value files.
    // Supports: strings, integers, floats, booleans. No tables, arrays, etc.
    const content = readFileSync(value, "utf-8");
    return parseSimpleTOML(content);
  }

  if (value.endsWith(".json")) {
    if (!existsSync(value)) return {};
    return JSON.parse(readFileSync(value, "utf-8"));
  }

  // JSON literal
  return JSON.parse(value);
}

/**
 * Minimal TOML parser — handles flat key = value files.
 * Supports: strings (quoted), integers, floats, booleans.
 */
function parseSimpleTOML(content: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const eqIdx = trimmed.indexOf("=");
    if (eqIdx < 0) continue;

    const key = trimmed.slice(0, eqIdx).trim();
    const rawVal = trimmed.slice(eqIdx + 1).trim();

    result[key] = parseTOMLValue(rawVal);
  }
  return result;
}

function parseTOMLValue(raw: string): unknown {
  // Boolean
  if (raw === "true") return true;
  if (raw === "false") return false;

  // Quoted string
  if ((raw.startsWith('"') && raw.endsWith('"')) ||
      (raw.startsWith("'") && raw.endsWith("'"))) {
    return raw.slice(1, -1);
  }

  // Number (integer or float)
  if (/^-?\d+\.\d+$/.test(raw)) return parseFloat(raw);
  if (/^-?\d+$/.test(raw)) return parseInt(raw, 10);

  return raw;
}

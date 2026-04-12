/**
 * Env var interpolation for config string values.
 *
 * Syntax:
 *   ${VAR}            -> process.env.VAR, or "" if unset
 *   ${VAR:-default}   -> process.env.VAR if set and non-empty, else default
 *   $$                -> literal "$"
 *
 * Bare `$` (not followed by `{`) is left as-is. Single-pass: the result of
 * one substitution is not re-scanned.
 */

const ENV_INTERP_RE = /\$\$|\$\{([^}]+)\}/g;

export function expandEnv(value: string): string {
  return value.replace(ENV_INTERP_RE, (match, expr: string | undefined) => {
    if (match === "$$") return "$";
    const idx = expr!.indexOf(":-");
    if (idx >= 0) {
      const key = expr!.slice(0, idx);
      const def = expr!.slice(idx + 2);
      const v = process.env[key];
      return v !== undefined && v !== "" ? v : def;
    }
    return process.env[expr!] ?? "";
  });
}

package config

import (
	"os"
	"regexp"
	"strings"
)

// envInterpRe matches either the literal-dollar escape `$$` or a `${...}`
// reference. The capture group is the expression inside the braces.
var envInterpRe = regexp.MustCompile(`\$\$|\$\{([^}]+)\}`)

// ExpandEnv interpolates `${VAR}` references in s against the process
// environment.
//
// Syntax:
//   - `${VAR}`           -> os.Getenv("VAR"), or "" if unset
//   - `${VAR:-default}`  -> os.Getenv("VAR") if set and non-empty, else default
//   - `$$`               -> literal "$"
//
// A bare `$` (not followed by `{`) is left as-is. The substitution is
// single-pass: the result of one expansion is not re-scanned.
func ExpandEnv(s string) string {
	return envInterpRe.ReplaceAllStringFunc(s, func(match string) string {
		if match == "$$" {
			return "$"
		}
		expr := match[2 : len(match)-1]
		if idx := strings.Index(expr, ":-"); idx >= 0 {
			key := expr[:idx]
			def := expr[idx+2:]
			if v, ok := os.LookupEnv(key); ok && v != "" {
				return v
			}
			return def
		}
		return os.Getenv(expr)
	})
}

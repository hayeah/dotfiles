// Package config provides single-envar config loading.
//
// One env var per app (<APP>_CONFIG). Value is either a file path
// (.json/.toml, detected by extension) or a JSON literal.
package config

import (
	"encoding/json"
	"os"
	"strings"

	"github.com/pelletier/go-toml/v2"
)

// Load reads config from the env var envVar.
//
// The value is interpreted as:
//   - File path ending .toml -> load as TOML
//   - File path ending .json -> load as JSON
//   - Anything else -> parse as JSON literal
//
// Returns an empty map when the env var is unset or empty, or when
// a file path doesn't exist.
func Load(envVar string) (map[string]any, error) {
	value := os.Getenv(envVar)
	if value == "" {
		return map[string]any{}, nil
	}

	if strings.HasSuffix(value, ".toml") {
		if _, err := os.Stat(value); os.IsNotExist(err) {
			return map[string]any{}, nil
		}
		data, err := os.ReadFile(value)
		if err != nil {
			return nil, err
		}
		var raw map[string]any
		if err := toml.Unmarshal(data, &raw); err != nil {
			return nil, err
		}
		return raw, nil
	}

	if strings.HasSuffix(value, ".json") {
		if _, err := os.Stat(value); os.IsNotExist(err) {
			return map[string]any{}, nil
		}
		data, err := os.ReadFile(value)
		if err != nil {
			return nil, err
		}
		var raw map[string]any
		if err := json.Unmarshal(data, &raw); err != nil {
			return nil, err
		}
		return raw, nil
	}

	// JSON literal
	var raw map[string]any
	if err := json.Unmarshal([]byte(value), &raw); err != nil {
		return nil, err
	}
	return raw, nil
}

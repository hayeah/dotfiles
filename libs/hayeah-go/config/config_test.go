package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type loadTest struct {
	Name         string          `json:"name"`
	EnvValue     *string         `json:"env_value"`
	FileContents *string         `json:"file_contents"`
	Expected     json.RawMessage `json:"expected"`
}

type testData struct {
	LoadTests []loadTest `json:"load_tests"`
}

func loadTestData(t *testing.T) testData {
	t.Helper()
	data, err := os.ReadFile("../../testdata/single-envar-config.json")
	if err != nil {
		t.Fatal(err)
	}
	var td testData
	if err := json.Unmarshal(data, &td); err != nil {
		t.Fatal(err)
	}
	return td
}

func TestLoad(t *testing.T) {
	td := loadTestData(t)
	envVar := "HAYEAH_TEST_CONFIG"

	for _, tc := range td.LoadTests {
		t.Run(tc.Name, func(t *testing.T) {
			os.Unsetenv(envVar)
			defer os.Unsetenv(envVar)

			if tc.EnvValue == nil {
				// env var unset
			} else if tc.FileContents != nil {
				// Write a temp file
				tmpDir := t.TempDir()
				var ext string
				if len(*tc.EnvValue) > 5 && (*tc.EnvValue)[len(*tc.EnvValue)-5:] == ".toml" {
					ext = ".toml"
				} else {
					ext = ".json"
				}
				filePath := filepath.Join(tmpDir, "config"+ext)
				if err := os.WriteFile(filePath, []byte(*tc.FileContents), 0o644); err != nil {
					t.Fatal(err)
				}
				os.Setenv(envVar, filePath)
			} else if tc.EnvValue != nil && len(*tc.EnvValue) > 0 && (*tc.EnvValue)[0] == '/' {
				// Missing file path
				os.Setenv(envVar, *tc.EnvValue)
			} else if tc.EnvValue != nil {
				os.Setenv(envVar, *tc.EnvValue)
			}

			result, err := Load(envVar)
			if err != nil {
				t.Fatal(err)
			}

			// Compare by marshaling both to JSON
			gotJSON, _ := json.Marshal(result)
			// Normalize expected
			var expected map[string]any
			if err := json.Unmarshal(tc.Expected, &expected); err != nil {
				t.Fatal(err)
			}
			expectedJSON, _ := json.Marshal(expected)

			if string(gotJSON) != string(expectedJSON) {
				t.Fatalf("got %s, want %s", gotJSON, expectedJSON)
			}
		})
	}
}

package config

import (
	"encoding/json"
	"os"
	"testing"
)

type expandEnvCase struct {
	Name     string            `json:"name"`
	Input    string            `json:"input"`
	Env      map[string]string `json:"env"`
	Expected string            `json:"expected"`
}

type expandEnvFixture struct {
	Cases []expandEnvCase `json:"expand_env_tests"`
}

func loadExpandEnvFixture(t *testing.T) expandEnvFixture {
	t.Helper()
	data, err := os.ReadFile("../../testdata/expand_env.json")
	if err != nil {
		t.Fatal(err)
	}
	var f expandEnvFixture
	if err := json.Unmarshal(data, &f); err != nil {
		t.Fatal(err)
	}
	return f
}

func TestExpandEnv(t *testing.T) {
	fixture := loadExpandEnvFixture(t)
	for _, tc := range fixture.Cases {
		t.Run(tc.Name, func(t *testing.T) {
			// t.Setenv records and restores the previous value automatically.
			for k, v := range tc.Env {
				t.Setenv(k, v)
			}
			got := ExpandEnv(tc.Input)
			if got != tc.Expected {
				t.Fatalf("ExpandEnv(%q) = %q, want %q", tc.Input, got, tc.Expected)
			}
		})
	}
}

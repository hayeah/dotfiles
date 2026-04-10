package fzfmatch

import (
	"encoding/json"
	"errors"
	"os"
	"sort"
	"testing"
)

type testData struct {
	SamplePaths       []string            `json:"sample_paths"`
	TermMatchTests    []termMatchTest     `json:"term_match_tests"`
	ParseErrorTests   []parseErrorTest    `json:"parse_error_tests"`
	ExpressionTests   []expressionTest    `json:"expression_tests"`
	WordBoundaryTests []wordBoundaryTest  `json:"word_boundary_tests"`
}

type termMatchTest struct {
	Name     string   `json:"name"`
	Pattern  string   `json:"pattern"`
	Expected []string `json:"expected"`
}

type parseErrorTest struct {
	Name    string `json:"name"`
	Pattern string `json:"pattern"`
}

type expressionTest struct {
	Name           string   `json:"name"`
	Pattern        string   `json:"pattern"`
	Paths          []string `json:"paths"`
	ExpectedSorted []string `json:"expected_sorted"`
}

type wordBoundaryTest struct {
	Name       string `json:"name"`
	S          string `json:"s"`
	Needle     string `json:"needle"`
	WordExact  bool   `json:"word_exact"`
	WordPrefix bool   `json:"word_prefix"`
}

func loadTestData(t *testing.T) testData {
	t.Helper()
	data, err := os.ReadFile("../../testdata/fzfmatch.json")
	if err != nil {
		t.Fatal(err)
	}
	var td testData
	if err := json.Unmarshal(data, &td); err != nil {
		t.Fatal(err)
	}
	return td
}

func TestTermMatch(t *testing.T) {
	td := loadTestData(t)
	for _, tc := range td.TermMatchTests {
		t.Run(tc.Name, func(t *testing.T) {
			m, err := ParseMatcher(tc.Pattern)
			if err != nil {
				t.Fatal(err)
			}
			got := m.Match(td.SamplePaths)
			if got == nil {
				got = []string{}
			}
			expected := tc.Expected
			if expected == nil {
				expected = []string{}
			}
			if len(got) != len(expected) {
				t.Fatalf("got %v, want %v", got, expected)
			}
			for i := range got {
				if got[i] != expected[i] {
					t.Fatalf("got %v, want %v", got, expected)
				}
			}
		})
	}
}

func TestParseErrors(t *testing.T) {
	td := loadTestData(t)
	for _, tc := range td.ParseErrorTests {
		t.Run(tc.Name, func(t *testing.T) {
			_, err := ParseMatcher(tc.Pattern)
			if err == nil {
				t.Fatal("expected error")
			}
			if !errors.Is(err, MatchError) {
				t.Fatalf("expected MatchError, got %v", err)
			}
		})
	}
}

func TestExpression(t *testing.T) {
	td := loadTestData(t)
	for _, tc := range td.ExpressionTests {
		t.Run(tc.Name, func(t *testing.T) {
			m, err := ParseMatcher(tc.Pattern)
			if err != nil {
				t.Fatal(err)
			}
			got := m.Match(tc.Paths)
			if got == nil {
				got = []string{}
			}
			sort.Strings(got)
			expected := tc.ExpectedSorted
			if expected == nil {
				expected = []string{}
			}
			if len(got) != len(expected) {
				t.Fatalf("got %v, want %v", got, expected)
			}
			for i := range got {
				if got[i] != expected[i] {
					t.Fatalf("got %v, want %v", got, expected)
				}
			}
		})
	}
}

func TestWordBoundary(t *testing.T) {
	td := loadTestData(t)
	t.Run("ContainsWordExact", func(t *testing.T) {
		for _, tc := range td.WordBoundaryTests {
			t.Run(tc.Name, func(t *testing.T) {
				got := ContainsWordExact(tc.S, tc.Needle)
				if got != tc.WordExact {
					t.Fatalf("ContainsWordExact(%q, %q) = %v, want %v", tc.S, tc.Needle, got, tc.WordExact)
				}
			})
		}
	})
	t.Run("ContainsWordPrefix", func(t *testing.T) {
		for _, tc := range td.WordBoundaryTests {
			t.Run(tc.Name, func(t *testing.T) {
				got := ContainsWordPrefix(tc.S, tc.Needle)
				if got != tc.WordPrefix {
					t.Fatalf("ContainsWordPrefix(%q, %q) = %v, want %v", tc.S, tc.Needle, got, tc.WordPrefix)
				}
			})
		}
	})
}

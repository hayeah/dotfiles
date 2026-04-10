// Package fzfmatch provides a non-interactive fuzzy path matcher inspired
// by fzf extended-search syntax. Deterministic boolean filter — no scoring,
// no ranking. Paths are matched case-insensitively with forward-slash
// normalization.
package fzfmatch

import (
	"errors"
	"fmt"
	"strings"
	"unicode"
)

// MatchError is returned when a pattern is malformed.
var MatchError = errors.New("match error")

// ---------------------------------------------------------------------------
// Word-boundary helpers
// ---------------------------------------------------------------------------

func isWordChar(ch rune) bool {
	return unicode.IsLetter(ch) || unicode.IsDigit(ch)
}

func hasWordBoundary(s string, idx, size int) bool {
	leftOK := idx == 0 || !isWordChar(rune(s[idx-1]))
	rightOK := idx+size == len(s) || !isWordChar(rune(s[idx+size]))
	return leftOK && rightOK
}

// ContainsWordExact returns true if needle appears in s bounded on both sides.
func ContainsWordExact(s, needle string) bool {
	if needle == "" {
		return false
	}
	start := 0
	for start <= len(s)-len(needle) {
		idx := strings.Index(s[start:], needle)
		if idx < 0 {
			break
		}
		idx += start
		if hasWordBoundary(s, idx, len(needle)) {
			return true
		}
		start = idx + 1
	}
	return false
}

// ContainsWordPrefix returns true if needle appears in s with a word boundary on the left.
func ContainsWordPrefix(s, needle string) bool {
	if needle == "" {
		return false
	}
	start := 0
	for start <= len(s)-len(needle) {
		idx := strings.Index(s[start:], needle)
		if idx < 0 {
			break
		}
		idx += start
		if idx == 0 || !isWordChar(rune(s[idx-1])) {
			return true
		}
		start = idx + 1
	}
	return false
}

// ---------------------------------------------------------------------------
// Term
// ---------------------------------------------------------------------------

type term struct {
	raw        string
	text       string
	anchorHead bool
	anchorTail bool
	wordPrefix bool
	wordExact  bool
	neg        bool
}

func parseTerm(raw string) (term, error) {
	t := term{raw: raw}
	p := raw

	// negation
	if strings.HasPrefix(p, "!") {
		t.neg = true
		p = p[1:]
		if p == "" {
			return t, fmt.Errorf("%w: empty term after negation in %q", MatchError, raw)
		}
	}

	// word-boundary quotes
	if strings.HasPrefix(p, "'") {
		p = p[1:]
		if p == "" {
			return t, fmt.Errorf("%w: empty term after leading quote in %q", MatchError, raw)
		}
		if strings.HasSuffix(p, "'") {
			t.wordExact = true
			p = p[:len(p)-1]
			if p == "" {
				return t, fmt.Errorf("%w: empty term in %q", MatchError, raw)
			}
		} else {
			t.wordPrefix = true
		}
	}

	// ./ as ^ anchor
	if strings.HasPrefix(p, "./") {
		t.anchorHead = true
		p = p[2:]
	}

	// ^ / $ anchors
	if strings.HasPrefix(p, "^") {
		t.anchorHead = true
		p = p[1:]
	}
	if strings.HasSuffix(p, "$") {
		t.anchorTail = true
		p = p[:len(p)-1]
	}

	if p == "" {
		return t, fmt.Errorf("%w: empty term after stripping modifiers in %q", MatchError, raw)
	}

	t.text = strings.ToLower(strings.ReplaceAll(p, "\\", "/"))
	return t, nil
}

func termMatches(t term, path string) bool {
	// exact path fast path
	if t.anchorHead && t.anchorTail && !t.wordExact && !t.wordPrefix {
		return path == t.text
	}

	sub := path
	if t.anchorHead {
		if !strings.HasPrefix(path, t.text) {
			return false
		}
		sub = path[:len(t.text)]
	}
	if t.anchorTail {
		if !strings.HasSuffix(path, t.text) {
			return false
		}
		sub = path[len(path)-len(t.text):]
	}

	if t.wordExact {
		return ContainsWordExact(sub, t.text)
	} else if t.wordPrefix {
		return ContainsWordPrefix(sub, t.text)
	}
	return strings.Contains(sub, t.text)
}

// ---------------------------------------------------------------------------
// Matcher
// ---------------------------------------------------------------------------

// Matcher filters a list of paths.
type Matcher interface {
	Match(paths []string) []string
}

// FuzzyMatcher matches paths against space-separated terms (implicit AND).
type FuzzyMatcher struct {
	Pattern string
	terms   []term
}

func (m *FuzzyMatcher) Match(paths []string) []string {
	if len(m.terms) == 0 {
		out := make([]string, len(paths))
		copy(out, paths)
		return out
	}

	var out []string
	for _, path := range paths {
		normal := strings.ToLower(strings.ReplaceAll(path, "\\", "/"))
		ok := true
		for _, t := range m.terms {
			matched := termMatches(t, normal)
			if t.neg {
				matched = !matched
			}
			if !matched {
				ok = false
				break
			}
		}
		if ok {
			out = append(out, path)
		}
	}
	return out
}

// CompoundMatcher chains matchers sequentially (AND / intersection).
type CompoundMatcher struct {
	Matchers []Matcher
}

func (m *CompoundMatcher) Match(paths []string) []string {
	current := paths
	for _, sub := range m.Matchers {
		current = sub.Match(current)
	}
	return current
}

// UnionMatcher merges results from all matchers (OR, deduplicated, first-seen order).
type UnionMatcher struct {
	Matchers []Matcher
}

func (m *UnionMatcher) Match(paths []string) []string {
	seen := make(map[string]bool)
	var out []string
	for _, sub := range m.Matchers {
		for _, p := range sub.Match(paths) {
			if !seen[p] {
				seen[p] = true
				out = append(out, p)
			}
		}
	}
	return out
}

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

func newFuzzyMatcher(pattern string) (*FuzzyMatcher, error) {
	pattern = strings.TrimSpace(pattern)
	if pattern == "" {
		return &FuzzyMatcher{Pattern: pattern}, nil
	}
	tokens := strings.Fields(pattern)
	terms := make([]term, 0, len(tokens))
	for _, tok := range tokens {
		t, err := parseTerm(tok)
		if err != nil {
			return nil, err
		}
		terms = append(terms, t)
	}
	return &FuzzyMatcher{Pattern: pattern, terms: terms}, nil
}

// ParseMatcher parses a pattern string into a Matcher.
//
// Operators:
//
//	| — compound AND (lower precedence, splits first)
//	; — union OR (higher precedence, binds tighter)
func ParseMatcher(pattern string) (Matcher, error) {
	pattern = strings.TrimSpace(pattern)

	// pipe = AND (lower precedence — checked first)
	if strings.Contains(pattern, "|") {
		parts := strings.Split(pattern, "|")
		var matchers []Matcher
		for _, p := range parts {
			if strings.TrimSpace(p) == "" {
				continue
			}
			m, err := ParseMatcher(p)
			if err != nil {
				return nil, err
			}
			matchers = append(matchers, m)
		}
		if len(matchers) == 0 {
			return nil, fmt.Errorf("%w: compound pattern contains no valid patterns", MatchError)
		}
		if len(matchers) == 1 {
			return matchers[0], nil
		}
		return &CompoundMatcher{Matchers: matchers}, nil
	}

	// semicolon = OR (higher precedence)
	if strings.Contains(pattern, ";") {
		parts := strings.Split(pattern, ";")
		var matchers []Matcher
		for _, p := range parts {
			if strings.TrimSpace(p) == "" {
				continue
			}
			m, err := ParseMatcher(p)
			if err != nil {
				return nil, err
			}
			matchers = append(matchers, m)
		}
		if len(matchers) == 0 {
			return nil, fmt.Errorf("%w: union pattern contains no valid patterns", MatchError)
		}
		if len(matchers) == 1 {
			return matchers[0], nil
		}
		return &UnionMatcher{Matchers: matchers}, nil
	}

	return newFuzzyMatcher(pattern)
}

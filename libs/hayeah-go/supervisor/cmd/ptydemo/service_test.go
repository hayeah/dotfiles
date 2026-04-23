package main

import (
	"slices"
	"testing"
)

func TestSanitizeChildEnvDropsTmux(t *testing.T) {
	in := []string{
		"PATH=/usr/bin",
		"TMUX=/tmp/tmux-501/default,1501,224",
		"TMUX_PANE=%42",
		"TERM=tmux-256color",
		"HOME=/Users/me",
	}
	out := sanitizeChildEnv(in)

	if slices.ContainsFunc(out, func(kv string) bool { return kv == "TMUX=/tmp/tmux-501/default,1501,224" }) {
		t.Fatal("TMUX leaked into child env")
	}
	if slices.ContainsFunc(out, func(kv string) bool { return kv == "TMUX_PANE=%42" }) {
		t.Fatal("TMUX_PANE leaked into child env")
	}
	for _, kv := range out {
		if kv == "TERM=tmux-256color" {
			t.Fatal("inherited TERM=tmux-256color was not overridden")
		}
	}
	if !slices.Contains(out, "TERM=xterm-256color") {
		t.Fatalf("child TERM not forced to xterm-256color; got %v", out)
	}
	// Unrelated vars must pass through.
	if !slices.Contains(out, "PATH=/usr/bin") {
		t.Fatal("PATH was dropped")
	}
	if !slices.Contains(out, "HOME=/Users/me") {
		t.Fatal("HOME was dropped")
	}
}

func TestSanitizeChildEnvWhenNotInTmux(t *testing.T) {
	in := []string{
		"PATH=/usr/bin",
		"TERM=xterm-ghostty",
	}
	out := sanitizeChildEnv(in)

	// TERM is overridden regardless — we always hand the child a
	// terminfo we know libghostty drives correctly.
	if slices.Contains(out, "TERM=xterm-ghostty") {
		t.Fatal("inherited TERM=xterm-ghostty was not overridden")
	}
	if !slices.Contains(out, "TERM=xterm-256color") {
		t.Fatalf("child TERM not forced to xterm-256color; got %v", out)
	}
}

func TestSanitizeChildEnvKeepsMalformedEntry(t *testing.T) {
	// Entries without '=' are legal-enough inputs from os.Environ()
	// on some platforms; sanitizer must pass them through untouched.
	in := []string{"BARE", "OK=1"}
	out := sanitizeChildEnv(in)
	if !slices.Contains(out, "BARE") {
		t.Fatal("bare entry without '=' was dropped")
	}
	if !slices.Contains(out, "OK=1") {
		t.Fatal("OK=1 was dropped")
	}
}

package supervisor

import (
	"os/exec"
	"strings"
	"testing"
	"time"
)

// TestTmuxPTYFeedCapture drives a TmuxPTY end-to-end against a real
// tmux server: create a detached session, wrap it as a PTY, send
// text, capture the pane, verify. Skipped when tmux isn't installed.
func TestTmuxPTYFeedCapture(t *testing.T) {
	if _, err := exec.LookPath("tmux"); err != nil {
		t.Skip("tmux not installed")
	}

	session := "sv-tmuxpty-test-" + strings.ReplaceAll(time.Now().Format("150405.000"), ".", "")
	tmux := &Tmux{}
	if err := tmux.NewSession(session, "", []string{"bash", "--norc", "--noprofile"}); err != nil {
		t.Fatalf("NewSession: %v", err)
	}
	t.Cleanup(func() { _ = tmux.KillSession(session) })

	target := session + ":0"
	pty := NewTmuxPTY(target)

	// Write raw bytes; they should land as typed characters in the
	// pane. Adding an empty SendKeys("") after is a noop — we don't
	// want to press Enter, just observe the echo.
	if err := pty.Write([]byte("hello world")); err != nil {
		t.Fatalf("Write: %v", err)
	}

	// Give tmux a beat to render.
	time.Sleep(150 * time.Millisecond)

	out, err := pty.Capture(10, false)
	if err != nil {
		t.Fatalf("Capture: %v", err)
	}
	if !strings.Contains(out, "hello world") {
		t.Errorf("capture did not contain feed; got:\n%s", out)
	}
}

// TestTmuxPTYResizeIsNoop asserts Resize does not error.
func TestTmuxPTYResizeIsNoop(t *testing.T) {
	pty := NewTmuxPTY("nonexistent:0")
	if err := pty.Resize(80, 24); err != nil {
		t.Errorf("Resize returned error: %v", err)
	}
}

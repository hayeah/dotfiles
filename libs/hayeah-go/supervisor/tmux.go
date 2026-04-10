package supervisor

import (
	"fmt"
	"os/exec"
	"strings"
)

// TmuxSpawn describes how to create the tmux window and what to run in it.
type TmuxSpawn struct {
	Session string            `json:"session"`
	Window  string            `json:"window,omitempty"`
	Cmd     []string          `json:"cmd"`
	CWD     string            `json:"cwd,omitempty"`
	Env     map[string]string `json:"env,omitempty"`
}

// Target returns the tmux target string "session:window".
func (s TmuxSpawn) Target() string {
	w := s.Window
	if w == "" {
		w = "0"
	}
	return s.Session + ":" + w
}

// Tmux is a thin wrapper over the tmux CLI.
type Tmux struct{}

// HasSession checks if a tmux session exists.
func (t *Tmux) HasSession(name string) bool {
	err := exec.Command("tmux", "has-session", "-t", name).Run()
	return err == nil
}

// HasWindow checks if a tmux window exists.
func (t *Tmux) HasWindow(target string) bool {
	err := exec.Command("tmux", "list-windows", "-t", target, "-F", "#{window_name}").Run()
	return err == nil
}

// NewSessionOrWindow creates the tmux session (if it doesn't exist) and
// then creates a window running the given command. If the session doesn't
// exist, the first window is created as part of session creation.
func (t *Tmux) NewSessionOrWindow(spawn TmuxSpawn) error {
	target := spawn.Target()
	window := spawn.Window
	if window == "" {
		window = "0"
	}

	// Build the shell command string with env injection
	shellCmd := t.buildShellCmd(spawn)

	if !t.HasSession(spawn.Session) {
		args := []string{"new-session", "-d", "-s", spawn.Session, "-n", window}
		if spawn.CWD != "" {
			args = append(args, "-c", spawn.CWD)
		}
		args = append(args, shellCmd)
		cmd := exec.Command("tmux", args...)
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("tmux new-session: %s: %w", out, err)
		}
		return nil
	}

	// Session exists — check if window already exists
	if t.HasWindow(target) {
		return fmt.Errorf("tmux window %q already exists", target)
	}

	args := []string{"new-window", "-t", spawn.Session, "-n", window}
	if spawn.CWD != "" {
		args = append(args, "-c", spawn.CWD)
	}
	args = append(args, shellCmd)
	cmd := exec.Command("tmux", args...)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("tmux new-window: %s: %w", out, err)
	}
	return nil
}

// KillWindow kills a tmux window by target.
func (t *Tmux) KillWindow(target string) error {
	cmd := exec.Command("tmux", "kill-window", "-t", target)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("tmux kill-window %q: %s: %w", target, out, err)
	}
	return nil
}

// CapturePane captures content from a tmux pane.
func (t *Tmux) CapturePane(target string, lines int) (string, error) {
	startLine := -lines
	cmd := exec.Command("tmux", "capture-pane", "-t", target, "-p",
		"-S", fmt.Sprintf("%d", startLine))
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("tmux capture-pane %q: %w", target, err)
	}
	return string(out), nil
}

// SendKeys sends keys to a tmux window.
func (t *Tmux) SendKeys(target string, keys ...string) error {
	args := append([]string{"send-keys", "-t", target}, keys...)
	cmd := exec.Command("tmux", args...)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("tmux send-keys %q: %s: %w", target, out, err)
	}
	return nil
}

// SendText sends text followed by Enter to a tmux window.
func (t *Tmux) SendText(target string, text string) error {
	return t.SendKeys(target, text, "Enter")
}

func (t *Tmux) buildShellCmd(spawn TmuxSpawn) string {
	var parts []string
	for k, v := range spawn.Env {
		parts = append(parts, fmt.Sprintf("export %s=%s;", k, shellQuote(v)))
	}
	for _, arg := range spawn.Cmd {
		parts = append(parts, shellQuote(arg))
	}
	return strings.Join(parts, " ")
}

func shellQuote(s string) string {
	if s == "" {
		return "''"
	}
	// Simple check: if the string has no special chars, return as-is
	safe := true
	for _, c := range s {
		if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
			c == '-' || c == '_' || c == '/' || c == '.' || c == ':' || c == '=' || c == ',') {
			safe = false
			break
		}
	}
	if safe {
		return s
	}
	return "'" + strings.ReplaceAll(s, "'", "'\"'\"'") + "'"
}

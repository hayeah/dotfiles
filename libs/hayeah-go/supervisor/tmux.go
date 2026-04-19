package supervisor

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"sort"
	"strings"
	"sync"
	"syscall"
)

// tmuxCreateMu serializes session/window creation across all Tmux
// instances in this process. Without it, two concurrent
// NewSessionOrWindow calls against the same session both observe
// HasSession == false, both invoke `tmux new-session -d`, and the
// second loses with "duplicate session". Window creation has the
// analogous race (both see HasWindow == false, both call
// new-window), though windows only collide when callers pick the
// same window name — this mutex closes both holes.
var tmuxCreateMu sync.Mutex

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

// NewSession creates a new detached tmux session running cmd in cwd.
func (t *Tmux) NewSession(name, cwd string, cmd []string) error {
	return t.NewSessionOrWindow(TmuxSpawn{
		Session: name,
		Window:  "0",
		CWD:     cwd,
		Cmd:     cmd,
	})
}

// HasSession checks if a tmux session exists.
func (t *Tmux) HasSession(name string) bool {
	return t.runQuiet("has-session", "-t", name) == nil
}

// HasWindow checks if a tmux window exists.
func (t *Tmux) HasWindow(target string) bool {
	return t.runQuiet("list-panes", "-t", target) == nil
}

// NewSessionOrWindow creates the tmux session (if it doesn't exist) and
// then creates a window running the given command. If the session doesn't
// exist, the first window is created as part of session creation.
func (t *Tmux) NewSessionOrWindow(spawn TmuxSpawn) error {
	// Serialize across goroutines so concurrent calls don't both try
	// to create the same session (or window).
	tmuxCreateMu.Lock()
	defer tmuxCreateMu.Unlock()

	target := spawn.Target()
	window := spawn.Window
	if window == "" {
		window = "0"
	}

	// Build the shell command string (no env injection — env is passed
	// natively via tmux -e KEY=VAL args below).
	shellCmd := t.buildShellCmd(spawn)
	envArgs := envFlags(spawn.Env)

	if !t.HasSession(spawn.Session) {
		args := []string{"new-session", "-d", "-s", spawn.Session, "-n", window}
		if spawn.CWD != "" {
			args = append(args, "-c", spawn.CWD)
		}
		args = append(args, envArgs...)
		args = append(args, shellCmd)
		return t.run(args...)
	}

	// Session exists — check if window already exists
	if t.HasWindow(target) {
		return fmt.Errorf("tmux window %q already exists", target)
	}

	args := []string{"new-window", "-t", spawn.Session, "-n", window}
	if spawn.CWD != "" {
		args = append(args, "-c", spawn.CWD)
	}
	args = append(args, envArgs...)
	args = append(args, shellCmd)
	return t.run(args...)
}

// RespawnPane replaces the process running in an existing tmux pane with
// a fresh invocation of the given command. Used by the restart-on-exit
// supervisor loop: the pane is preserved (same target, same window) but
// the dead child is replaced by a new spawn. `-k` kills any still-running
// process first (in the normal restart flow there is none; the pane is
// already at an exit prompt).
//
// Env handling: `respawn-pane` has no `-e` flag of its own. The respawned
// process inherits the window's environment set via `-e` at new-window
// time, which matches the "restart ≠ reconfigure" intuition — rerunning
// the command does not re-seed env.
func (t *Tmux) RespawnPane(target string, spawn TmuxSpawn) error {
	shellCmd := t.buildShellCmd(spawn)
	args := []string{"respawn-pane", "-k", "-t", target}
	if spawn.CWD != "" {
		args = append(args, "-c", spawn.CWD)
	}
	args = append(args, shellCmd)
	return t.run(args...)
}

// KillSession kills a tmux session.
func (t *Tmux) KillSession(target string) error {
	return t.run("kill-session", "-t", target)
}

// KillWindow kills a tmux window by target.
func (t *Tmux) KillWindow(target string) error {
	return t.run("kill-window", "-t", target)
}

// CapturePane captures content from a tmux pane.
func (t *Tmux) CapturePane(target string, lines int) (string, error) {
	startLine := -lines
	return t.output("capture-pane", "-t", target, "-p",
		"-S", fmt.Sprintf("%d", startLine))
}

// CapturePan is a compatibility alias for CapturePane.
func (t *Tmux) CapturePan(target string, lines int) (string, error) {
	return t.CapturePane(target, lines)
}

// CapturePaneEscapes captures pane content including ANSI escape sequences.
func (t *Tmux) CapturePaneEscapes(target string, lines int) (string, error) {
	startLine := -lines
	out, err := t.output("capture-pane", "-t", target, "-p", "-e", "-S", fmt.Sprintf("%d", startLine))
	if err != nil {
		return "", err
	}
	return out, nil
}

// SendKeys sends keys to a tmux window.
func (t *Tmux) SendKeys(target string, keys ...string) error {
	args := append([]string{"send-keys", "-t", target}, keys...)
	return t.run(args...)
}

// SendText sends literal text to a tmux window without pressing Enter.
func (t *Tmux) SendText(target string, text string) error {
	return t.run("send-keys", "-t", target, "-l", text)
}

// PasteBuffer pastes text through a tmux buffer.
func (t *Tmux) PasteBuffer(target, text string) error {
	bufName := "supervisor-paste"
	if err := t.run("set-buffer", "-b", bufName, "--", text); err != nil {
		return err
	}
	return t.run("paste-buffer", "-b", bufName, "-d", "-t", target)
}

// CurrentTarget returns the current tmux session:window target.
func (t *Tmux) CurrentTarget() (string, error) {
	return t.output("display-message", "-p", "#S:#W")
}

// Attach replaces the current process with tmux attach/switch-client.
func (t *Tmux) Attach(target string) error {
	parts := strings.SplitN(target, ":", 2)
	if len(parts) == 2 {
		_ = t.runQuiet("select-window", "-t", target)
	}
	session := parts[0]

	tmuxPath, err := exec.LookPath("tmux")
	if err != nil {
		return err
	}
	if os.Getenv("TMUX") != "" {
		return syscall.Exec(tmuxPath, []string{"tmux", "switch-client", "-t", session}, os.Environ())
	}
	return syscall.Exec(tmuxPath, []string{"tmux", "attach-session", "-t", session}, os.Environ())
}

func (t *Tmux) run(args ...string) error {
	cmd := exec.Command("tmux", args...)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("tmux %s: %s: %w", strings.Join(args, " "), out, err)
	}
	return nil
}

func (t *Tmux) runQuiet(args ...string) error {
	cmd := exec.Command("tmux", args...)
	cmd.Stdout = io.Discard
	cmd.Stderr = io.Discard
	return cmd.Run()
}

func (t *Tmux) output(args ...string) (string, error) {
	cmd := exec.Command("tmux", args...)
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("tmux %s: %w", strings.Join(args, " "), err)
	}
	return strings.TrimRight(string(out), "\n"), nil
}

func (t *Tmux) buildShellCmd(spawn TmuxSpawn) string {
	parts := make([]string, 0, len(spawn.Cmd))
	for _, arg := range spawn.Cmd {
		parts = append(parts, shellQuote(arg))
	}
	return strings.Join(parts, " ")
}

// envFlags renders spawn.Env as tmux `-e KEY=VAL` argv in sorted key
// order (reproducible output for tests and debugging). Returns an empty
// slice when env is nil/empty.
func envFlags(env map[string]string) []string {
	if len(env) == 0 {
		return nil
	}
	keys := make([]string, 0, len(env))
	for k := range env {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	out := make([]string, 0, 2*len(keys))
	for _, k := range keys {
		out = append(out, "-e", k+"="+env[k])
	}
	return out
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

package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/creack/pty"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
)

// createSessionReq is the JSON body accepted by POST /api/sessions.
//
//	cmd:  shell-style string, tokenized with single/double-quote
//	      grouping (no escapes). First token = program, rest = argv.
//	argv: pre-tokenized []string alternative to `cmd`. If both are
//	      set, argv wins (so the webui never has to think about
//	      quoting when it already has the right array).
//	key:  optional — if provided and unique, used as the session id;
//	      otherwise autoKey picks one.
type createSessionReq struct {
	Cmd  string   `json:"cmd,omitempty"`
	Argv []string `json:"argv,omitempty"`
	Key  string   `json:"key,omitempty"`
}

func (s *serveState) createSession(w http.ResponseWriter, r *http.Request) {
	var body createSessionReq
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, "bad body: "+err.Error(), http.StatusBadRequest)
		return
	}
	argv := body.Argv
	if len(argv) == 0 {
		body.Cmd = strings.TrimSpace(body.Cmd)
		if body.Cmd == "" {
			http.Error(w, "cmd (or argv) is required", http.StatusBadRequest)
			return
		}
		parsed, perr := splitCmd(body.Cmd)
		if perr != nil {
			http.Error(w, "parse cmd: "+perr.Error(), http.StatusBadRequest)
			return
		}
		argv = parsed
	}
	if len(argv) == 0 {
		http.Error(w, "cmd has no tokens", http.StatusBadRequest)
		return
	}
	key := body.Key
	if key == "" {
		key = autoKey(argv[0])
	}
	if s.store.IsAlive(key) {
		http.Error(w, fmt.Sprintf("session %q already alive", key), http.StatusConflict)
		return
	}

	sockPath, err := spawnSupervise(s.stateDir, key, argv)
	if err != nil {
		http.Error(w, "spawn: "+err.Error(), http.StatusInternalServerError)
		return
	}

	// Read back the freshly-written state.json so the webui can
	// populate its optimistic row with real data (pid, created_at).
	st, err := s.store.Load(key)
	if err != nil {
		http.Error(w, "load state after spawn: "+err.Error(), http.StatusInternalServerError)
		return
	}

	type resp struct {
		*supervisor.StateFile
		Alive      bool   `json:"alive"`
		SocketPath string `json:"socket_path"`
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(resp{
		StateFile:  st,
		Alive:      true,
		SocketPath: sockPath,
	})
}

func (s *serveState) closeSession(w http.ResponseWriter, r *http.Request) {
	key := r.PathValue("key")
	if key == "" {
		http.Error(w, "missing session key", http.StatusBadRequest)
		return
	}
	st, err := s.store.Load(key)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	if st.Supervisor.PID == 0 {
		http.Error(w, "state.json has no supervisor pid", http.StatusConflict)
		return
	}

	proc, err := os.FindProcess(st.Supervisor.PID)
	if err != nil {
		http.Error(w, "find process: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if err := proc.Signal(syscall.SIGTERM); err != nil {
		// ESRCH = already gone; treat as success.
		if !errors.Is(err, os.ErrProcessDone) {
			http.Error(w, "sigterm: "+err.Error(), http.StatusInternalServerError)
			return
		}
	}
	w.WriteHeader(http.StatusNoContent)
}

// spawnSupervise forks `ptydemo supervise` as a detached grandchild.
// Mirrors cmdRun but without the attach; returns the rpc.sock path
// once the supervisor has written it.
func spawnSupervise(stateDir, key string, argv []string) (string, error) {
	master, slave, err := pty.Open()
	if err != nil {
		return "", fmt.Errorf("pty.Open: %w", err)
	}
	defer master.Close()
	defer slave.Close()
	// 80x24 is the HTTP spawn default. The webui should resize to
	// its actual dimensions on attach via the WS resize message.
	if err := pty.Setsize(slave, &pty.Winsize{Cols: 80, Rows: 24}); err != nil {
		return "", fmt.Errorf("setsize: %w", err)
	}

	self, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("os.Executable: %w", err)
	}
	superviseArgs := []string{"supervise", "--state-dir", stateDir, "--key", key, "--"}
	superviseArgs = append(superviseArgs, argv...)

	cmd := exec.Command(self, superviseArgs...)
	cmd.Stdin = slave
	cmd.Stdout = slave
	cmd.Stderr = slave
	cmd.ExtraFiles = []*os.File{master}
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setsid:  true,
		Setctty: true,
		Ctty:    0,
	}
	if err := cmd.Start(); err != nil {
		return "", fmt.Errorf("fork supervise: %w", err)
	}
	// Let the grandchild live on its own; the serve process should
	// not wait on it.
	_ = cmd.Process.Release()

	sockPath := filepath.Join(stateDir, key, "rpc.sock")
	if err := waitForSocket(sockPath, 3*time.Second); err != nil {
		return "", err
	}
	return sockPath, nil
}

// splitCmd is a shell-ish tokenizer: whitespace separates tokens,
// single- and double-quoted runs are grouped together (with the
// quotes stripped). No backslash escaping — quotes inside quotes
// must use the other flavor. Good enough for every common webui
// input (`bash`, `bash -l`, `sh -c "echo hi | wc -l"`, `sh -c
// 'echo "hi"'`); the demo doesn't need full POSIX parsing.
func splitCmd(s string) ([]string, error) {
	var out []string
	var cur []rune
	var quote rune // 0 = not quoted; else the opening quote char

	flush := func() {
		if len(cur) > 0 {
			out = append(out, string(cur))
			cur = cur[:0]
		}
	}

	for _, r := range s {
		if quote != 0 {
			if r == quote {
				quote = 0
				continue
			}
			cur = append(cur, r)
			continue
		}
		switch {
		case r == '"' || r == '\'':
			quote = r
		case r == ' ' || r == '\t' || r == '\n':
			flush()
		default:
			cur = append(cur, r)
		}
	}
	if quote != 0 {
		return nil, fmt.Errorf("unterminated %c-quoted string", quote)
	}
	flush()
	return out, nil
}


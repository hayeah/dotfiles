package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
)

// RunCmdService is the reference Service for ptydemo: spawn one
// child, publish state transitions (starting → running → exited),
// return when the child exits. No restart, no briefing, no idle
// detection — the library's three-interface contract in its
// simplest possible shape.
//
// Consumers (agentboss, devport) will write their own richer
// Services on top of the same Supervisor/PTY interfaces.
type RunCmdService struct {
	Cmd  string   // program name
	Args []string // argv[1:]
}

// runState is the JSON shape published to state.json.State. The
// webui reads `cmd` for the sidebar subtitle and `state` for the
// dot tone. `pid` is the child's PID (not the supervisor's —
// that's in SupervisorState.PID).
type runState struct {
	State     string `json:"state"` // "starting" | "running" | "exited"
	Cmd       string `json:"cmd"`
	PID       int    `json:"pid,omitempty"`
	ExitCode  int    `json:"exit_code,omitempty"`
	StartedAt string `json:"started_at,omitempty"`
	ExitedAt  string `json:"exited_at,omitempty"`
}

func (s *RunCmdService) cmdString() string {
	parts := append([]string{s.Cmd}, s.Args...)
	return strings.Join(parts, " ")
}

// Run implements supervisor.Service. Stdin/Stdout/Stderr are
// inherited from __supervise, which is already wired to the PTY
// slave (by the parent `ptydemo run` via exec.Cmd.ExtraFiles +
// SysProcAttr). So cmd.Start() puts the child inside the PTY
// automatically.
func (s *RunCmdService) Run(ctx context.Context, super supervisor.Supervisor) error {
	if s.Cmd == "" {
		return errors.New("RunCmdService: Cmd is required")
	}

	started := time.Now().UTC().Format(time.RFC3339)
	state := runState{
		State:     "starting",
		Cmd:       s.cmdString(),
		StartedAt: started,
	}
	if err := super.UpdateState(state); err != nil {
		return fmt.Errorf("publish starting: %w", err)
	}

	cmd := exec.CommandContext(ctx, s.Cmd, s.Args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	// Child becomes its own session leader with the slave (fd 0)
	// as its controlling tty. This is the emulator pattern:
	// supervise (us) holds the master but is session-less for
	// this tty, so TIOCSWINSZ on the master keeps working even
	// after the child's job-control setup (tcsetpgrp) takes
	// the fg pgrp away from us. Without Setctty here, the
	// master-side ioctl would start returning EIO on macOS as
	// soon as an interactive shell had configured itself.
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setsid:  true,
		Setctty: true,
		Ctty:    0,
	}
	// Polite shutdown: SIGTERM on ctx cancel, then SIGKILL after
	// WaitDelay if the child ignores us. exec.Cmd.Cancel is the
	// Go 1.20+ hook for this.
	cmd.Cancel = func() error {
		return cmd.Process.Signal(syscall.SIGTERM)
	}
	cmd.WaitDelay = 5 * time.Second

	if err := cmd.Start(); err != nil {
		state.State = "exited"
		state.ExitCode = -1
		state.ExitedAt = time.Now().UTC().Format(time.RFC3339)
		_ = super.UpdateState(state)
		return fmt.Errorf("start %q: %w", s.Cmd, err)
	}

	state.State = "running"
	state.PID = cmd.Process.Pid
	if err := super.UpdateState(state); err != nil {
		return fmt.Errorf("publish running: %w", err)
	}

	waitErr := cmd.Wait()

	state.State = "exited"
	state.ExitedAt = time.Now().UTC().Format(time.RFC3339)
	if waitErr != nil {
		var exitErr *exec.ExitError
		if errors.As(waitErr, &exitErr) {
			state.ExitCode = exitErr.ExitCode()
		} else {
			state.ExitCode = -1
		}
	}
	_ = super.UpdateState(state)
	return nil
}

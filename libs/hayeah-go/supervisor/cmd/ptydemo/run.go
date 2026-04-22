package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/creack/pty"
	"golang.org/x/term"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor/ptyclient"
)

// cmdRun opens a PTY pair, forks `ptydemo supervise` with the
// slave as stdio and the master on fd 3, and either:
//
//   - if --attach (default true when stdin is a tty), attaches the
//     caller's terminal to the fresh session via ptyclient, or
//   - prints the session key and exits immediately.
//
// The detach chord (Ctrl-\ .) returns from the attach loop; the
// supervisor keeps running in the background.
func cmdRun(args []string) error {
	fs := flag.NewFlagSet("run", flag.ContinueOnError)
	stateDir := fs.String("state-dir", defaultStateDir(), "session state directory")
	key := fs.String("key", "", "session key (default: auto from cmd name + timestamp)")
	attach := fs.Bool("attach", true, "attach stdio after spawn (ignored if stdin is not a tty)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	rest := fs.Args()
	if len(rest) == 0 {
		return errors.New("run: missing command after --")
	}
	if *key == "" {
		*key = autoKey(rest[0])
	}

	// Fail fast if a session with this key already holds the flock.
	store := supervisor.NewStore(*stateDir)
	if store.IsAlive(*key) {
		return fmt.Errorf("run: session %q is already alive — pick a different --key or kill it first", *key)
	}

	// Size the PTY to the caller's terminal if possible; otherwise
	// 80x24 is a safe default.
	cols, rows := uint16(80), uint16(24)
	if term.IsTerminal(int(os.Stdin.Fd())) {
		c, r, err := term.GetSize(int(os.Stdin.Fd()))
		if err == nil {
			cols, rows = uint16(c), uint16(r)
		}
	}

	// Open PTY pair; configure slave size so ioctl TIOCGWINSZ
	// returns sane values to the child.
	master, slave, err := pty.Open()
	if err != nil {
		return fmt.Errorf("pty.Open: %w", err)
	}
	if err := pty.Setsize(slave, &pty.Winsize{Cols: cols, Rows: rows}); err != nil {
		master.Close()
		slave.Close()
		return fmt.Errorf("setsize: %w", err)
	}

	// Re-exec ourselves with argv[1] = "supervise". We launch the
	// current binary so the supervise flow is statically linked to
	// the run flow — no PATH lookup.
	self, err := os.Executable()
	if err != nil {
		master.Close()
		slave.Close()
		return fmt.Errorf("os.Executable: %w", err)
	}
	superviseArgs := []string{
		"supervise",
		"--state-dir", *stateDir,
		"--key", *key,
		"--",
	}
	superviseArgs = append(superviseArgs, rest...)

	cmd := exec.Command(self, superviseArgs...)
	cmd.Stdin = slave
	cmd.Stdout = slave
	cmd.Stderr = slave
	cmd.ExtraFiles = []*os.File{master}
	// Supervise runs in its own session (Setsid) but is NOT the
	// controlling process of the tty — the Service (inside
	// supervise) will do Setctty when it spawns the actual
	// child. Keeping supervise session-less for this tty is the
	// emulator pattern; it's what lets TIOCSWINSZ on the master
	// keep working after the child claims the fg pgrp.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}

	if err := cmd.Start(); err != nil {
		master.Close()
		slave.Close()
		return fmt.Errorf("fork supervise: %w", err)
	}

	// Parent is done with the slave and the master — the child
	// has its own references through the fork.
	_ = slave.Close()
	_ = master.Close()

	// Wait for rpc.sock to appear (bounded by a 3-second budget).
	sockPath := filepath.Join(*stateDir, *key, "rpc.sock")
	if err := waitForSocket(sockPath, 3*time.Second); err != nil {
		return fmt.Errorf("run: supervise did not open socket: %w", err)
	}

	if !*attach || !term.IsTerminal(int(os.Stdin.Fd())) {
		fmt.Fprintf(os.Stderr, "ptydemo: session %q started (state-dir=%s)\n", *key, *stateDir)
		fmt.Println(*key)
		// Detach: release the child by the OS (Release, not Wait).
		// The supervise process continues in its own session.
		_ = cmd.Process.Release()
		return nil
	}

	// Attach immediately.
	_ = cmd.Process.Release()
	client := ptyclient.NewClient(sockPath)
	defer client.Close()

	ctx, stop := context.WithCancel(context.Background())
	defer stop()
	return client.AttachStdio(ctx, ptyclient.AttachOptions{})
}

// autoKey builds a key from the command basename + a short
// timestamp suffix. Conservative rules: lowercase, letters / digits
// / dashes only.
func autoKey(cmdName string) string {
	base := filepath.Base(cmdName)
	safe := strings.Map(func(r rune) rune {
		switch {
		case r >= 'a' && r <= 'z':
			return r
		case r >= 'A' && r <= 'Z':
			return r + 32
		case r >= '0' && r <= '9':
			return r
		case r == '-' || r == '_':
			return r
		default:
			return '-'
		}
	}, base)
	if safe == "" {
		safe = "sess"
	}
	suffix := strconv.FormatInt(time.Now().Unix()%100000, 10)
	return safe + "-" + suffix
}

// waitForSocket polls for the unix socket file to appear. The
// supervise process creates rpc.sock as the last step before
// entering Service.Run — seeing it is a strong signal that the
// supervisor is ready.
func waitForSocket(path string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(path); err == nil {
			return nil
		}
		time.Sleep(25 * time.Millisecond)
	}
	return fmt.Errorf("timeout waiting for %s", path)
}

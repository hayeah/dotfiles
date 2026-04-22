package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"

	"github.com/creack/pty"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
)

// cmdSupervise is the internal worker that actually holds the
// flock, owns the PTY emulator, and serves rpc.sock. It is not
// meant to be invoked by hand; `ptydemo run` forks this with:
//
//   - stdin/stdout/stderr pointing at the PTY slave
//   - fd 3 = the PTY master (ExtraFiles[0])
//   - setsid so it's the controlling process of its own session
//
// Flags tell it which state dir / key to use and (after `--`)
// what command to run.
func cmdSupervise(args []string) error {
	fs := flag.NewFlagSet("supervise", flag.ContinueOnError)
	stateDir := fs.String("state-dir", defaultStateDir(), "session state directory")
	key := fs.String("key", "", "session key (required)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *key == "" {
		return errors.New("--key is required")
	}
	rest := fs.Args()
	if len(rest) == 0 {
		return errors.New("supervise: missing command after --")
	}

	// fd 3 is the PTY master, handed down by the parent via
	// ExtraFiles. If the caller botched the fork we fall back with
	// a clear error rather than segfaulting later.
	master := os.NewFile(3, "pty-master")
	if master == nil {
		return errors.New("supervise: PTY master not provided on fd 3 (invoked outside `ptydemo run`?)")
	}

	// Seed the emulator's grid from the kernel winsize that the
	// parent set on the slave. If we can't read it (should never
	// happen), pick a sane default.
	cols, rows := uint16(80), uint16(24)
	if size, err := pty.GetsizeFull(master); err == nil && size.Cols > 0 && size.Rows > 0 {
		cols, rows = size.Cols, size.Rows
	}

	ptyImpl, err := supervisor.NewLibghosttyPTY(master, cols, rows)
	if err != nil {
		return fmt.Errorf("new libghostty pty: %w", err)
	}
	defer ptyImpl.Close()

	svc := &RunCmdService{
		Cmd:  rest[0],
		Args: rest[1:],
	}

	run := supervisor.New(supervisor.SupervisorConfig{
		StateDir: *stateDir,
		Key:      *key,
		Service:  svc,
		PTY:      ptyImpl,
	})

	return run.Run(context.Background())
}

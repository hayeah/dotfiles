package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"syscall"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
)

func cmdKill(args []string) error {
	fs := flag.NewFlagSet("kill", flag.ContinueOnError)
	stateDir := fs.String("state-dir", defaultStateDir(), "session state directory")
	if err := fs.Parse(args); err != nil {
		return err
	}
	rest := fs.Args()
	if len(rest) != 1 {
		return errors.New("kill: exactly one session key required")
	}

	store := supervisor.NewStore(*stateDir)
	st, err := store.Resolve(rest[0])
	if err != nil {
		return err
	}
	if st.Supervisor.PID == 0 {
		return errors.New("kill: state.json has no supervisor pid")
	}

	proc, err := os.FindProcess(st.Supervisor.PID)
	if err != nil {
		return fmt.Errorf("find process %d: %w", st.Supervisor.PID, err)
	}
	if err := proc.Signal(syscall.SIGTERM); err != nil {
		return fmt.Errorf("sigterm %d: %w", st.Supervisor.PID, err)
	}
	fmt.Fprintf(os.Stderr, "ptydemo: sent SIGTERM to %s (pid %d)\n", st.Supervisor.Key, st.Supervisor.PID)
	return nil
}

package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor/ptyclient"
)

func cmdAttach(args []string) error {
	fs := flag.NewFlagSet("attach", flag.ContinueOnError)
	stateDir := fs.String("state-dir", defaultStateDir(), "session state directory")
	if err := fs.Parse(args); err != nil {
		return err
	}
	rest := fs.Args()
	if len(rest) != 1 {
		return errors.New("attach: exactly one session key required")
	}
	key := rest[0]

	store := supervisor.NewStore(*stateDir)
	// Resolve prefix → full key. This mirrors the agentboss ergonomic
	// (type the first few chars instead of the whole id).
	st, err := store.Resolve(key)
	if err != nil {
		return err
	}
	if !store.IsAlive(st.Supervisor.Key) {
		return fmt.Errorf("attach: session %q is not alive (supervisor has exited)", st.Supervisor.Key)
	}

	sockPath := filepath.Join(*stateDir, st.Supervisor.Key, "rpc.sock")
	if _, err := os.Stat(sockPath); err != nil {
		return fmt.Errorf("attach: no rpc.sock at %s", sockPath)
	}

	client := ptyclient.NewClient(sockPath)
	defer client.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	return client.AttachStdio(ctx, ptyclient.AttachOptions{})
}

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"text/tabwriter"
	"time"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
)

func cmdLs(args []string) error {
	fs := flag.NewFlagSet("ls", flag.ContinueOnError)
	stateDir := fs.String("state-dir", defaultStateDir(), "session state directory")
	if err := fs.Parse(args); err != nil {
		return err
	}

	store := supervisor.NewStore(*stateDir)
	states, err := store.List()
	if err != nil {
		return err
	}
	if len(states) == 0 {
		fmt.Fprintln(os.Stderr, "(no sessions)")
		return nil
	}

	tw := tabwriter.NewWriter(os.Stdout, 0, 2, 2, ' ', 0)
	fmt.Fprintln(tw, "KEY\tALIVE\tSTATE\tPID\tCMD\tSTARTED")
	for _, st := range states {
		alive := "no"
		if store.IsAlive(st.Supervisor.Key) {
			alive = "yes"
		}
		// State.json's "state" field is whatever the Service wrote;
		// we know the shape (runState) from RunCmdService. Best-
		// effort decode — if a different Service shape wrote this
		// directory we fall back to the raw string.
		var rs runState
		_ = json.Unmarshal(st.State, &rs)
		fmt.Fprintf(tw, "%s\t%s\t%s\t%d\t%s\t%s\n",
			st.Supervisor.Key,
			alive,
			emptyAs(rs.State, "-"),
			rs.PID,
			emptyAs(rs.Cmd, "-"),
			st.Supervisor.CreatedAt.Local().Format(time.Stamp),
		)
	}
	return tw.Flush()
}

func emptyAs(s, fallback string) string {
	if s == "" {
		return fallback
	}
	return s
}

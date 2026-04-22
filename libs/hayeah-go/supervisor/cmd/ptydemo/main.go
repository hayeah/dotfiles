// Command ptydemo is a bounded, self-contained consumer of the
// supervisor library — the e2e proof that Runner + LibghosttyPTY +
// ptyclient work end-to-end for both terminal and browser attach
// surfaces.
//
// Subcommands:
//
//	ptydemo run [flags] -- <cmd> [args...]   spawn a session
//	ptydemo supervise [flags]                 (internal worker)
//	ptydemo ls                                 list sessions
//	ptydemo attach <key>                       terminal attach
//	ptydemo kill <key>                         SIGTERM by pid
//	ptydemo serve [--addr :8080]               web UI + WS bridge
//
// See spec.md §"Demo app (cmd/ptydemo)" for the design.
package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	cmd := os.Args[1]
	args := os.Args[2:]

	var err error
	switch cmd {
	case "run":
		err = cmdRun(args)
	case "supervise":
		err = cmdSupervise(args)
	case "ls":
		err = cmdLs(args)
	case "attach":
		err = cmdAttach(args)
	case "kill":
		err = cmdKill(args)
	case "serve":
		err = cmdServe(args)
	case "-h", "--help", "help":
		usage()
		return
	default:
		fmt.Fprintf(os.Stderr, "ptydemo: unknown subcommand %q\n\n", cmd)
		usage()
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "ptydemo %s: %v\n", cmd, err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprint(os.Stderr, `ptydemo — demo app for the hayeah-go/supervisor library

Usage:
  ptydemo run [--state-dir=~/.ptydemo] [--key=<id>] [--attach=true] -- <cmd> [args...]
  ptydemo supervise --state-dir <d> --key <k> -- <cmd> [args...]   (internal)
  ptydemo ls [--state-dir=~/.ptydemo]
  ptydemo attach <key> [--state-dir=~/.ptydemo]
  ptydemo kill <key> [--state-dir=~/.ptydemo]
  ptydemo serve --port <n> [--addr=127.0.0.1] [--state-dir=~/.ptydemo] [--prefix=/api]
`)
}

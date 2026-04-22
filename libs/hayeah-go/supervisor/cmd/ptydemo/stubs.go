package main

import (
	"errors"
	"os"
	"path/filepath"
)

// defaultStateDir resolves to ~/.ptydemo (not /tmp — session state
// should survive a reboot for the demo).
func defaultStateDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ".ptydemo"
	}
	return filepath.Join(home, ".ptydemo")
}

// Subcommand stubs. `serve` (serve.go) lands first so the web
// preview can iterate against a real API even while run / attach /
// kill are still scaffolded.

func cmdRun(args []string) error {
	return errors.New("ptydemo run: not yet implemented")
}

func cmdSupervise(args []string) error {
	return errors.New("ptydemo supervise: not yet implemented")
}

func cmdLs(args []string) error {
	return errors.New("ptydemo ls: not yet implemented")
}

func cmdAttach(args []string) error {
	return errors.New("ptydemo attach: not yet implemented")
}

func cmdKill(args []string) error {
	return errors.New("ptydemo kill: not yet implemented")
}

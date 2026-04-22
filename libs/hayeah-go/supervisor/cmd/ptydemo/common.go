package main

import (
	"os"
	"path/filepath"
)

// defaultStateDir resolves to ~/.ptydemo (not /tmp — session state
// should survive a reboot for the demo). All subcommands share
// this default so sessions started by `ptydemo run` are visible to
// `ptydemo ls` / `attach` / `kill` / `serve` without extra flags.
func defaultStateDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ".ptydemo"
	}
	return filepath.Join(home, ".ptydemo")
}

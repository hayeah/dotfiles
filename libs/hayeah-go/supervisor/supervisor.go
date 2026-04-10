package supervisor

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

// SupervisorConfig configures a Supervisor instance.
type SupervisorConfig struct {
	StateDir   string    // base dir (e.g. .devport/)
	Key        string    // this service's key (e.g. "vite")
	Spawn      TmuxSpawn // how to create the tmux window + what to run
	Plugin     Plugin    // monitors the running service, reports state (optional)
	KillOnExit bool      // kill tmux window when supervisor exits (default false)
}

// Supervisor coordinates a single supervised process.
type Supervisor struct {
	cfg    SupervisorConfig
	tmux   *Tmux
	writer *Writer
	log    *slog.Logger
}

// New creates a Supervisor from the given config.
func New(cfg SupervisorConfig) *Supervisor {
	return &Supervisor{
		cfg:  cfg,
		tmux: &Tmux{},
		log:  slog.Default().With("supervisor", cfg.Key),
	}
}

// Run starts the child in a tmux window, monitors it, and blocks until
// ctx is cancelled or a termination signal is received.
//
// Flow:
//  1. Create <StateDir>/<Key>/ directory
//  2. Acquire dir flock via OpenWriter
//  3. Create tmux session (if needed) + window
//  4. Write initial state.json
//  5. If Plugin != nil: run plugin goroutine
//  6. Forward signals (SIGINT, SIGTERM, SIGHUP) to tmux window
//  7. Wait for ctx cancellation or signal
//  8. Cleanup: release flock, optionally kill tmux window
func (s *Supervisor) Run(ctx context.Context) error {
	stateDir := filepath.Join(s.cfg.StateDir, s.cfg.Key)

	// 1. Create state directory
	if err := os.MkdirAll(stateDir, 0755); err != nil {
		return fmt.Errorf("create state dir: %w", err)
	}

	// 2. Acquire dir flock
	initial := StateFile{
		Supervisor: SupervisorState{
			Key:       s.cfg.Key,
			Spawn:     s.cfg.Spawn,
			CreatedAt: time.Now(),
		},
	}
	writer, err := OpenWriter(stateDir, initial)
	if err != nil {
		return fmt.Errorf("open writer: %w", err)
	}
	s.writer = writer
	defer writer.Close()

	s.log.Info("acquired flock", "dir", stateDir)

	// 3. Create tmux window
	spawn := s.cfg.Spawn
	if spawn.Window == "" {
		spawn.Window = s.cfg.Key
	}
	if err := s.tmux.NewSessionOrWindow(spawn); err != nil {
		return fmt.Errorf("create tmux window: %w", err)
	}
	target := spawn.Target()
	s.log.Info("created tmux window", "target", target)

	if s.cfg.KillOnExit {
		defer func() {
			s.log.Info("killing tmux window", "target", target)
			s.tmux.KillWindow(target)
		}()
	}

	// 4. Initial state already written by OpenWriter

	// 5. Run plugin if provided
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	pluginDone := make(chan error, 1)
	if s.cfg.Plugin != nil {
		env := PluginEnv{
			UpdateService: func(state any) error {
				return writer.UpdateService(state)
			},
			Tmux:     s.tmux,
			Target:   target,
			StateDir: stateDir,
		}
		go func() {
			pluginDone <- s.cfg.Plugin.Run(ctx, env)
		}()
	}

	// 6. Forward signals
	sigCh := make(chan os.Signal, 3)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
	defer signal.Stop(sigCh)

	// 7. Wait for completion
	select {
	case err := <-pluginDone:
		s.log.Info("plugin exited", "err", err)
		return err
	case sig := <-sigCh:
		s.log.Info("received signal", "signal", sig)
		cancel() // cancel plugin context
		select {
		case <-pluginDone:
		case <-time.After(5 * time.Second):
			s.log.Warn("plugin did not exit within 5s after signal")
		}
		return fmt.Errorf("terminated by signal: %s", sig)
	case <-ctx.Done():
		s.log.Info("context cancelled")
		select {
		case <-pluginDone:
		case <-time.After(5 * time.Second):
			s.log.Warn("plugin did not exit within 5s after cancel")
		}
		return ctx.Err()
	}
}

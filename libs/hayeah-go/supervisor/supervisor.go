package supervisor

import (
	"context"
	"encoding/json"
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
	StateDir       string    // base dir (e.g. .devport/)
	Key            string    // this service's key (e.g. "vite")
	Spawn          TmuxSpawn // how to create the tmux window + what to run
	Plugin         Plugin    // monitors the running service, reports state (optional)
	KillOnExit     bool      // kill tmux window when supervisor exits (default false)
	SocketHandlers map[string]func(w *Writer) func(rw interface{ Write([]byte) }, r interface{}) // custom RPC handlers
}

// Supervisor coordinates a single supervised process.
type Supervisor struct {
	cfg    SupervisorConfig
	tmux   *Tmux
	bus    *EventBus
	writer *Writer
	log    *slog.Logger
}

// New creates a Supervisor from the given config.
func New(cfg SupervisorConfig) *Supervisor {
	return &Supervisor{
		cfg:  cfg,
		tmux: &Tmux{},
		bus:  NewEventBus(),
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
//  5. Open unix socket for SSE events
//  6. If Plugin != nil: run plugin goroutine
//  7. Forward signals (SIGINT, SIGTERM, SIGHUP) to tmux window
//  8. Wait for ctx cancellation or signal
//  9. Cleanup: close socket, release flock, optionally kill tmux window
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

	// 5. Open unix socket
	socketPath := filepath.Join(stateDir, "rpc.sock")
	socket, err := ListenSocket(socketPath, s.bus, nil)
	if err != nil {
		s.log.Warn("failed to open socket", "err", err)
		// non-fatal — continue without socket
	} else {
		defer socket.Close()
		s.log.Info("listening on socket", "path", socketPath)
	}

	// Publish initial state event
	s.publishState()

	// 6. Run plugin if provided
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	pluginDone := make(chan error, 1)
	if s.cfg.Plugin != nil {
		env := PluginEnv{
			UpdateService: func(state any) error {
				if err := writer.UpdateService(state); err != nil {
					return err
				}
				s.publishState()
				return nil
			},
			Bus:      s.bus,
			Tmux:     s.tmux,
			Target:   target,
			StateDir: stateDir,
		}
		go func() {
			pluginDone <- s.cfg.Plugin.Run(ctx, env)
		}()
	}

	// 7. Forward signals
	sigCh := make(chan os.Signal, 3)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
	defer signal.Stop(sigCh)

	// 8. Wait for completion
	select {
	case err := <-pluginDone:
		s.log.Info("plugin exited", "err", err)
		s.bus.Publish(Event{
			Type: "exited",
			Data: json.RawMessage(fmt.Sprintf(`{"error":%q}`, fmt.Sprint(err))),
		})
		return err
	case sig := <-sigCh:
		s.log.Info("received signal", "signal", sig)
		cancel() // cancel plugin context
		// Wait briefly for plugin to finish
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

// Bus returns the event bus for external use.
func (s *Supervisor) Bus() *EventBus {
	return s.bus
}

func (s *Supervisor) publishState() {
	state := s.writer.Snapshot()
	data, err := json.Marshal(&state)
	if err != nil {
		return
	}
	s.bus.Publish(Event{Type: "state", Data: json.RawMessage(data)})
}

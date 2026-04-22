package supervisor

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

// SupervisorConfig configures a Supervisor instance.
type SupervisorConfig struct {
	StateDir       string    // base dir (e.g. .devport/)
	Key            string    // this service's key (e.g. "vite")
	Spawn          TmuxSpawn // how to create the tmux window + what to run
	InitialService any       // optional initial value for the "service" section
	Plugin         Plugin    // monitors the running service, reports state (optional)
	KillOnExit     bool      // kill tmux window when supervisor exits (default false)

	// RestartOnExit, if true, respawns the tmux pane and re-runs the
	// plugin when the supervised child exits. Used for infrastructure
	// processes (boss agent, dashboard) that should survive a kill and
	// self-heal during dev iteration.
	RestartOnExit bool

	// PluginFactory, if set, is called to construct a fresh Plugin on
	// each (re)spawn. Required when RestartOnExit is true — the existing
	// Plugin field is single-shot and can't be reused across iterations.
	// When RestartOnExit is false, only Plugin is consulted.
	PluginFactory func() Plugin

	// Briefings is a list of messages replayed to the child after each
	// (re)spawn. The first message is sent on the cycle's first idle;
	// each subsequent message is sent on the next idle transition (i.e.
	// once the child has finished processing the previous one). Used to
	// reconstruct operational context for a boss-style agent after a
	// kill, and to chain follow-up commands (e.g. an opening briefing
	// plus a slash-command toggle) into a single setup script. Each
	// message is sent via `tmux send-keys -l <text>` + Enter. Empty/nil
	// = no replay.
	Briefings []string

	// OnIdle, if set, is called once per spawn cycle the first time the
	// plugin publishes state=="idle". Used by callers to drive
	// per-cycle side effects (briefing replay is built-in; this hook is
	// for tests + custom integrations).
	OnIdle func(cycle int)
}

// Runner is the concrete supervisor entry point. It will be reshaped
// in the forthcoming PTY-backend refactor; the type was previously
// exported as `Supervisor` but that name is being reclaimed for the
// new interface that Services receive. Behavior is unchanged from
// the pre-refactor `Supervisor` struct.
type Runner struct {
	cfg    SupervisorConfig
	tmux   *Tmux
	writer *Writer
	log    *slog.Logger
}

// New creates a Runner from the given config.
func New(cfg SupervisorConfig) *Runner {
	return &Runner{
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
func (s *Runner) Run(ctx context.Context) error {
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
	if s.cfg.InitialService != nil {
		data, err := json.Marshal(s.cfg.InitialService)
		if err != nil {
			return fmt.Errorf("marshal initial service: %w", err)
		}
		initial.Service = json.RawMessage(data)
	}
	writer, err := OpenWriter(stateDir, initial)
	if err != nil {
		return fmt.Errorf("open writer: %w", err)
	}
	s.writer = writer
	defer writer.Close()

	s.log.Info("acquired flock", "dir", stateDir)

	// 3. Create tmux window (first iteration). Subsequent restart
	//    iterations use respawn-pane to re-run the command in place.
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

	// 5. Forward signals
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	sigCh := make(chan os.Signal, 3)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
	defer signal.Stop(sigCh)

	// 6. Run plugin loop (one iteration unless RestartOnExit + PluginFactory).
	for cycle := 0; ; cycle++ {
		if cycle > 0 {
			// Two restart shapes: (1) the user Ctrl-C'd the child but
			// tmux kept the pane open → respawn-pane reuses it; (2) the
			// window is gone entirely → recreate it. We probe and pick.
			if s.tmux.HasWindow(target) {
				s.log.Info("respawning tmux pane", "target", target, "cycle", cycle)
				if err := s.tmux.RespawnPane(target, spawn); err != nil {
					s.log.Warn("respawn-pane failed", "err", err)
					return fmt.Errorf("respawn pane: %w", err)
				}
			} else {
				s.log.Info("recreating tmux window", "target", target, "cycle", cycle)
				if err := s.tmux.NewSessionOrWindow(spawn); err != nil {
					return fmt.Errorf("recreate tmux window: %w", err)
				}
			}
		}

		plugin := s.pluginForCycle(cycle)

		// Per-cycle idle observer: wraps UpdateService to detect every
		// rising edge (non-idle → idle) and fire OnIdle + the next
		// briefing message. The first rising edge fires OnIdle and the
		// first briefing; each subsequent edge (after the previous
		// briefing has been processed and the child is back at the
		// prompt) fires the next message in s.cfg.Briefings.
		var prevIdle bool
		var idleCount int
		var nextBriefingIdx int
		env := PluginEnv{
			UpdateService: func(state any) error {
				if err := writer.UpdateService(state); err != nil {
					return err
				}
				currentlyIdle := isIdleState(state)
				if !prevIdle && currentlyIdle {
					idleCount++
					if idleCount == 1 && s.cfg.OnIdle != nil {
						s.cfg.OnIdle(cycle)
					}
					if nextBriefingIdx < len(s.cfg.Briefings) {
						msg := s.cfg.Briefings[nextBriefingIdx]
						idx := nextBriefingIdx
						nextBriefingIdx++
						go s.sendBriefingMessage(cycle, idx, target, msg)
					}
				}
				prevIdle = currentlyIdle
				return nil
			},
			Tmux:     s.tmux,
			Target:   target,
			StateDir: stateDir,
		}

		pluginDone := make(chan error, 1)
		if plugin != nil {
			go func() { pluginDone <- plugin.Run(ctx, env) }()
		} else {
			// No plugin: block until signal or ctx.
			close(pluginDone)
		}

		select {
		case err := <-pluginDone:
			s.log.Info("plugin exited", "err", err, "cycle", cycle)
			if !s.cfg.RestartOnExit || ctx.Err() != nil {
				return err
			}
			// Loop for next respawn iteration.
		case sig := <-sigCh:
			s.log.Info("received signal", "signal", sig)
			cancel()
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
}

// pluginForCycle returns the Plugin to use for this iteration. Restart
// cycles require a fresh instance because plugins typically hold single-
// shot state (sync.Once, channels, bound sockets).
func (s *Runner) pluginForCycle(cycle int) Plugin {
	if s.cfg.PluginFactory != nil {
		return s.cfg.PluginFactory()
	}
	if cycle == 0 {
		return s.cfg.Plugin
	}
	// Subsequent cycles without a factory: reuse Plugin (caller's risk).
	return s.cfg.Plugin
}

// sendBriefingMessage types one briefing message into the pane and presses
// Enter. Called from the UpdateService callback's goroutine on each rising
// idle edge so we don't block the plugin's hot path.
func (s *Runner) sendBriefingMessage(cycle, idx int, target, msg string) {
	if msg == "" {
		return
	}
	// Small delay so the agent's input box is settled before typing.
	time.Sleep(500 * time.Millisecond)
	if err := s.tmux.SendText(target, msg); err != nil {
		s.log.Warn("briefing send-text failed", "err", err, "cycle", cycle, "idx", idx)
		return
	}
	if err := s.tmux.SendKeys(target, "Enter"); err != nil {
		s.log.Warn("briefing send-enter failed", "err", err, "cycle", cycle, "idx", idx)
		return
	}
	s.log.Info("briefing message sent", "target", target, "cycle", cycle, "idx", idx)
}

// isIdleState inspects a marshaled service-state payload for a top-level
// `state` field equal to "idle". The payload is whatever the plugin
// passed to UpdateService — typically a struct with a State string.
func isIdleState(v any) bool {
	data, err := json.Marshal(v)
	if err != nil {
		return false
	}
	// Cheap string probe first to avoid a full re-unmarshal on every tick.
	if !strings.Contains(string(data), `"idle"`) {
		return false
	}
	var probe struct {
		State string `json:"state"`
	}
	if err := json.Unmarshal(data, &probe); err != nil {
		return false
	}
	return probe.State == "idle"
}

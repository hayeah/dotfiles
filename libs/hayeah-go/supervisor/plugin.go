package supervisor

import "context"

// Plugin starts a service, monitors it, and reports state.
// The supervisor calls Run() after acquiring the flock and setting up
// the tmux window. The plugin is responsible for:
//   - Monitoring the running process (tail logs, health checks, etc.)
//   - Reporting state via UpdateService()
//   - Creating any sockets/files it needs in StateDir (e.g. rpc.sock)
//   - Returning when ctx is cancelled or the service exits
type Plugin interface {
	Run(ctx context.Context, env PluginEnv) error
}

// PluginEnv provides infrastructure to the plugin during Run().
type PluginEnv struct {
	UpdateService func(state any) error // atomically rewrites the "service" section
	Tmux          *Tmux                 // capture pane content, send keys
	Target        string                // tmux target "session:window"
	StateDir      string                // <base>/<key>/ for transcripts, logs, etc.
}

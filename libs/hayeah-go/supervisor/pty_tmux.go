package supervisor

// TmuxPTY is the tmux-backed PTY transport. The __supervise process
// is expected to already be running inside a tmux pane (spawned via
// `tmux new-window 'foo __supervise ...'` by the consumer). Writes
// flow through `tmux send-keys` and `tmux paste-buffer`; snapshots
// come from `tmux capture-pane`.
//
// TmuxPTY contributes no HTTP routes to Supervisor.Mux(): tmux is
// itself an attach target, so there's no ws<->pty bridge to expose.
// Dashboards bridging to tmux sessions use `tmux attach` directly.
type TmuxPTY struct {
	tmux   *Tmux
	target string // "session:window"
}

// NewTmuxPTY wraps an existing tmux pane identified by
// "session:window" as a PTY. Caller is responsible for having
// already created the pane (typically via `tmux new-window` that
// spawns this __supervise process as its command).
func NewTmuxPTY(target string) *TmuxPTY {
	return &TmuxPTY{tmux: &Tmux{}, target: target}
}

// Target returns the underlying tmux target. Services that need
// tmux-specific affordances (e.g. `tmux select-pane`, custom
// `capture-pane` flags) can hold the concrete *TmuxPTY and use it.
func (p *TmuxPTY) Target() string { return p.target }

// Write sends literal bytes to the pane as if typed. Large writes
// go through paste-buffer to avoid send-keys argv limits and
// newline-splitting surprises.
func (p *TmuxPTY) Write(data []byte) error {
	const pasteThreshold = 1024
	if len(data) > pasteThreshold {
		return p.tmux.PasteBuffer(p.target, string(data))
	}
	return p.tmux.SendText(p.target, string(data))
}

// SendKeys passes keys to `tmux send-keys`. Tmux's own key-name
// parser handles "C-a", "Enter", "hello" etc.
func (p *TmuxPTY) SendKeys(keys ...string) error {
	return p.tmux.SendKeys(p.target, keys...)
}

// Capture returns the pane's current content. withEscapes=true
// preserves ANSI color/attribute codes (tmux -e flag).
func (p *TmuxPTY) Capture(lines int, withEscapes bool) (string, error) {
	if withEscapes {
		return p.tmux.CapturePaneEscapes(p.target, lines)
	}
	return p.tmux.CapturePane(p.target, lines)
}

// Resize is a noop for tmux: tmux manages pane size natively when
// clients attach. The method exists to satisfy the PTY interface;
// callers who need to resize the tmux pane programmatically should
// hold the concrete *Tmux and issue a `resize-window` or
// `resize-pane` themselves.
func (p *TmuxPTY) Resize(cols, rows uint16) error {
	_ = cols
	_ = rows
	return nil
}

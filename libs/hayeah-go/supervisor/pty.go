package supervisor

// PTY is the terminal transport for a supervised child's stdio.
//
// Two implementations ship with the library:
//   - TmuxPTY:       the supervisor process runs inside an existing
//                    tmux pane; I/O flows through `tmux send-keys` /
//                    `capture-pane`.
//   - LibghosttyPTY: the supervisor opens its own PTY and runs
//                    Ghostty's VT parser (via hauntty/libghostty)
//                    against the byte stream. Contributes HTTP
//                    routes (`/pty/{input,resize,send-keys,stream,
//                    snapshot,scrollback}`) to Supervisor.Mux().
//
// Consumers construct the concrete impl they want and pass it via
// SupervisorConfig.PTY. Services reach it through super.PTY().
//
// There is no Attach(cmd) method: the `__supervise` process always
// starts with its stdio pointing at a PTY (tmux: from
// `tmux new-window`; libghostty: from the parent `run` command
// opening a PTY before forking). A Service's cmd.Start() inherits
// fd 0/1/2 by default and ends up inside the PTY in both cases.
type PTY interface {
	// Write sends raw bytes to the PTY master. Passthrough for
	// large pastes and raw escape sequences.
	Write(data []byte) error

	// SendKeys translates tmux-style key names (e.g. "C-a", "Enter",
	// "hello") into the right on-the-wire bytes for the current
	// emulator mode, and writes them. Mode-aware.
	SendKeys(keys ...string) error

	// Capture returns a textual rendering of the current screen.
	// withEscapes=true preserves ANSI color/attribute sequences;
	// false returns plain text.
	Capture(lines int, withEscapes bool) (string, error)

	// Resize informs the underlying PTY + emulator of a new window
	// size. For TmuxPTY this is a noop (tmux handles resize
	// natively when clients attach); for LibghosttyPTY it updates
	// the master winsize and the emulator's grid.
	Resize(cols, rows uint16) error
}

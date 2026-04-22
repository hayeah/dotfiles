package supervisor

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"sync"

	"code.selman.me/hauntty/libghostty"
	"github.com/creack/pty"
)

// LibghosttyPTY is the PTY-backend that owns its own PTY master fd
// and runs Ghostty's VT parser (via hauntty/libghostty, transpiled
// from Zig to Go-over-WASM via ncruces/wasm2go — pure Go at runtime,
// no cgo) against the byte stream.
//
// Construction flow: the parent process (e.g. `ptydemo run`) opens
// a PTY pair via github.com/creack/pty, forks __supervise with
// Stdin/Stdout/Stderr = slave and ExtraFiles = [master]. Inside
// __supervise, the master file arrives at fd 3:
//
//	master := os.NewFile(3, "pty-master")
//	pty := NewLibghosttyPTY(master, cols, rows)
//
// The Service's exec.Cmd.Start inherits stdio from __supervise,
// which is already on the slave, so the child ends up inside the
// PTY automatically.
//
// Concurrency model: a single dispatcher goroutine owns the
// *libghostty.Terminal (the libghostty WASM runtime is not
// thread-safe). Reader and Capture/Resize/subscribe calls all
// funnel through the dispatcher via an actions channel. Multiple
// simultaneous Capture calls are safe but will serialize.
//
// The PTY master itself is fine to Write from multiple goroutines
// (kernel handles that), so Write doesn't go through the dispatcher.
type LibghosttyPTY struct {
	master *os.File
	rt     *libghostty.Runtime
	term   *libghostty.Terminal

	mu   sync.RWMutex
	cols uint16
	rows uint16

	// actions are single-threaded-access closures against term +
	// subs. Send-only from outside the dispatcher goroutine.
	actions chan func()

	subs map[chan []byte]struct{} // owned by dispatcher goroutine

	doneOnce sync.Once
	done     chan struct{}
}

// NewLibghosttyPTY wraps an existing PTY master file as a PTY.
// Caller retains ownership of master's lifecycle (closing master
// on shutdown is caller's responsibility; typically Runner.Run
// closes the PTY via Close which then cancels the emulator).
//
// cols and rows are the initial screen size. They should match the
// kernel-level winsize on the master (which the caller set via
// pty.Setsize before handing the master to this constructor).
func NewLibghosttyPTY(master *os.File, cols, rows uint16) (*LibghosttyPTY, error) {
	if master == nil {
		return nil, errors.New("libghostty: master is nil")
	}
	rt, err := libghostty.NewRuntime()
	if err != nil {
		return nil, fmt.Errorf("new runtime: %w", err)
	}
	// Scrollback of 1000 lines matches the spec's "in-memory only,
	// matches tmux behavior" guidance — hauntty uses the same.
	term, err := rt.NewTerminal(uint32(cols), uint32(rows), 1000)
	if err != nil {
		rt.Close()
		return nil, fmt.Errorf("new terminal: %w", err)
	}
	p := &LibghosttyPTY{
		master:  master,
		rt:      rt,
		term:    term,
		cols:    cols,
		rows:    rows,
		actions: make(chan func(), 64),
		subs:    make(map[chan []byte]struct{}),
		done:    make(chan struct{}),
	}
	go p.dispatch()
	go p.readLoop()
	return p, nil
}

// Close signals the dispatcher to shut down: it closes outstanding
// subscriber channels and tears down the emulator. The master file
// is NOT closed here — the caller owns it. After Close, any
// pending do() calls will return without running fn.
//
// Safe to call multiple times; only the first Close performs the
// shutdown.
func (p *LibghosttyPTY) Close() error {
	p.doneOnce.Do(func() {
		// Schedule a final shutdown action that cleans up subs +
		// emulator, then close p.done so do() stops submitting.
		shutdown := make(chan struct{})
		select {
		case p.actions <- func() {
			for ch := range p.subs {
				delete(p.subs, ch)
				close(ch)
			}
			_ = p.term.Close()
			_ = p.rt.Close()
			close(shutdown)
		}:
			<-shutdown
		default:
			// Dispatcher already past the point of accepting; best
			// effort — subs will leak until process exit, emulator
			// finalized by GC.
		}
		close(p.done)
	})
	return nil
}

// dispatch is the single goroutine that owns the emulator + subs.
// All Feed / Resize / DumpScreen / subscribe / unsubscribe calls
// route through here. Exits when p.done closes AND the actions
// queue has been drained (any in-flight action still completes).
func (p *LibghosttyPTY) dispatch() {
	for {
		select {
		case <-p.done:
			// Drain any remaining queued actions so callers that
			// already sent before Close don't hang on their done
			// channel.
			for {
				select {
				case action := <-p.actions:
					action()
				default:
					return
				}
			}
		case action := <-p.actions:
			action()
		}
	}
}

// do runs fn on the dispatcher goroutine and waits for it to
// complete. Use for any operation that touches p.term or p.subs.
// If the PTY is closed, do returns without running fn.
func (p *LibghosttyPTY) do(fn func()) {
	done := make(chan struct{})
	select {
	case <-p.done:
		return
	default:
	}
	select {
	case p.actions <- func() {
		fn()
		close(done)
	}:
		<-done
	case <-p.done:
		return
	}
}

// readLoop reads from the master, feeds bytes through the
// emulator, and fans out to /pty/stream subscribers. Exits when
// the master is closed (EOF) or the PTY is Close()d.
func (p *LibghosttyPTY) readLoop() {
	buf := make([]byte, 4096)
	for {
		n, err := p.master.Read(buf)
		if n > 0 {
			chunk := append([]byte{}, buf[:n]...)
			p.do(func() {
				_ = p.term.Feed(chunk)
				for ch := range p.subs {
					select {
					case ch <- chunk:
					default:
						// Drop on slow subscriber. They'll resync
						// on next reattach (fresh snapshot).
					}
				}
			})
		}
		if err != nil {
			// EOF or master closed — emulator and subs cleaned up
			// via Close.
			if err != io.EOF {
				// Non-EOF errors are typically "file already
				// closed" during shutdown. Nothing actionable.
			}
			return
		}
	}
}

// Write sends raw bytes to the PTY master. Safe to call from any
// goroutine (kernel-side); does not touch the emulator (the
// emulator only sees bytes that come back from the child — if
// anything, user input produces echo that flows through readLoop
// in the normal terminal model).
func (p *LibghosttyPTY) Write(data []byte) error {
	_, err := p.master.Write(data)
	return err
}

// SendKeys translates tmux-style key names to the right on-the-wire
// bytes using libghostty's EncodeKey (mode-aware — handles kitty
// keyboard / modify-other-keys protocols). Unknown names are
// written as literal bytes (matches tmux's "type the string"
// fallback).
func (p *LibghosttyPTY) SendKeys(keys ...string) error {
	for _, k := range keys {
		keyCode, mods, known := keyNameToCode(k)
		if !known {
			if _, err := p.master.Write([]byte(k)); err != nil {
				return err
			}
			continue
		}
		var bytes []byte
		var err error
		p.do(func() {
			bytes, err = p.term.EncodeKey(keyCode, mods)
		})
		if err != nil {
			return fmt.Errorf("encode key %q: %w", k, err)
		}
		if _, err := p.master.Write(bytes); err != nil {
			return err
		}
	}
	return nil
}

// Capture returns a textual dump of the current screen. The lines
// argument is advisory — libghostty dumps the full current screen
// plus an optional scrollback flag; we don't currently slice by
// line count.
func (p *LibghosttyPTY) Capture(lines int, withEscapes bool) (string, error) {
	format := libghostty.DumpPlain
	if withEscapes {
		format = libghostty.DumpVTSafe
	}
	var out string
	var err error
	p.do(func() {
		var dump *libghostty.ScreenDump
		dump, err = p.term.DumpScreen(format)
		if err == nil {
			out = string(dump.Data)
		}
	})
	_ = lines // TODO: honor lines once libghostty exposes a line range.
	return out, err
}

// Resize updates both the kernel-level PTY winsize and the
// emulator's grid. Called by HTTP /pty/resize and directly by
// consumers.
func (p *LibghosttyPTY) Resize(cols, rows uint16) error {
	if err := pty.Setsize(p.master, &pty.Winsize{Cols: cols, Rows: rows}); err != nil {
		return fmt.Errorf("setsize: %w", err)
	}
	var termErr error
	p.do(func() {
		termErr = p.term.Resize(uint32(cols), uint32(rows))
	})
	if termErr != nil {
		return fmt.Errorf("term resize: %w", termErr)
	}
	p.mu.Lock()
	p.cols, p.rows = cols, rows
	p.mu.Unlock()
	return nil
}

// Size returns the current (cols, rows). Convenience for HTTP
// handlers.
func (p *LibghosttyPTY) Size() (cols, rows uint16) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.cols, p.rows
}

// Snapshot returns the current screen as ANSI bytes (DumpVTFull).
// This is what subscribers see as their first chunk on /pty/stream
// so that they render a faithful current screen before live bytes
// start flowing.
func (p *LibghosttyPTY) Snapshot() ([]byte, error) {
	var out []byte
	var err error
	p.do(func() {
		var dump *libghostty.ScreenDump
		dump, err = p.term.DumpScreen(libghostty.DumpVTFull)
		if err == nil {
			out = append([]byte{}, dump.Data...)
		}
	})
	return out, err
}

// ScrollbackText returns plain-text scrollback (DumpPlain |
// DumpFlagScrollback). lines is advisory and currently ignored.
func (p *LibghosttyPTY) ScrollbackText(lines int) (string, error) {
	var out string
	var err error
	p.do(func() {
		var dump *libghostty.ScreenDump
		dump, err = p.term.DumpScreen(libghostty.DumpPlain | libghostty.DumpFlagScrollback)
		if err == nil {
			out = string(dump.Data)
		}
	})
	_ = lines
	return out, err
}

// subscribe registers a channel to receive live PTY bytes. Returns
// the channel and a cancel function. Called by /pty/stream.
func (p *LibghosttyPTY) subscribe() (<-chan []byte, func()) {
	ch := make(chan []byte, 64)
	p.do(func() {
		p.subs[ch] = struct{}{}
	})
	cancel := func() {
		p.do(func() {
			if _, ok := p.subs[ch]; ok {
				delete(p.subs, ch)
				close(ch)
			}
		})
	}
	return ch, cancel
}

// RegisterRoutes contributes /pty/{input,resize,send-keys,stream,
// snapshot,scrollback} to the supervisor's mux. Runner.Run invokes
// this automatically if the configured PTY implements it — see the
// type assertion in supervisor.go.
func (p *LibghosttyPTY) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/pty/input", p.handleInput)
	mux.HandleFunc("/pty/resize", p.handleResize)
	mux.HandleFunc("/pty/send-keys", p.handleSendKeys)
	mux.HandleFunc("/pty/stream", p.handleStream)
	mux.HandleFunc("/pty/snapshot", p.handleSnapshot)
	mux.HandleFunc("/pty/scrollback", p.handleScrollback)
}

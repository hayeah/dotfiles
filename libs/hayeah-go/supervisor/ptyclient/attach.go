package ptyclient

import (
	"context"
	"errors"
	"io"
	"os"
	"os/signal"
	"sync"
	"syscall"

	"golang.org/x/term"
)

// AttachOptions tunes AttachStdio. Zero values are the defaults.
type AttachOptions struct {
	// DetachChord is the byte sequence that detaches the attach
	// loop without sending bytes to the PTY. Defaults to
	// []byte{0x1c, '.'} — i.e. Ctrl-\ then period. Must be exactly
	// two bytes; the first byte is the prefix, the second
	// distinguishes a detach from a pass-through. An empty slice
	// disables the chord (attach only exits on ctx cancel).
	DetachChord []byte

	// Stdin / Stdout override the default os.Stdin / os.Stdout.
	// Useful for tests. If either is nil the os default is used.
	Stdin  *os.File
	Stdout io.Writer
}

// AttachStdio puts the caller's terminal into raw mode, bridges
// os.Stdin<->PTY input and PTY output<->os.Stdout, forwards
// SIGWINCH to the remote PTY via /pty/resize, and returns when
// either ctx is cancelled or the detach chord is typed.
//
// The PTY's snapshot is delivered as the first bytes of the stream,
// so the terminal renders its current state faithfully on attach /
// reattach.
//
// Errors from the underlying streams cause AttachStdio to return
// that error wrapped; a clean detach via the chord returns nil.
func (c *Client) AttachStdio(ctx context.Context, opts AttachOptions) error {
	stdin := opts.Stdin
	if stdin == nil {
		stdin = os.Stdin
	}
	stdout := opts.Stdout
	if stdout == nil {
		stdout = os.Stdout
	}
	chord := opts.DetachChord
	if chord == nil {
		chord = []byte{0x1c, '.'} // Ctrl-\ then .
	}

	// Raw mode on stdin, so we pass keystrokes byte-for-byte
	// without line-buffering or signal interpretation. Restore on
	// return.
	stdinFD := int(stdin.Fd())
	var oldState *term.State
	if term.IsTerminal(stdinFD) {
		st, err := term.MakeRaw(stdinFD)
		if err != nil {
			return err
		}
		oldState = st
		defer term.Restore(stdinFD, oldState)
	}

	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Start a goroutine that watches SIGWINCH and pushes new
	// sizes through Resize.
	var wg sync.WaitGroup
	if term.IsTerminal(stdinFD) {
		winchCh := make(chan os.Signal, 1)
		signal.Notify(winchCh, syscall.SIGWINCH)
		// Emit the initial size so the remote lines up with our
		// terminal without the user having to resize.
		if cols, rows, err := term.GetSize(stdinFD); err == nil {
			_ = c.ResizeContext(ctx, uint16(cols), uint16(rows))
		}
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer signal.Stop(winchCh)
			for {
				select {
				case <-ctx.Done():
					return
				case <-winchCh:
					cols, rows, err := term.GetSize(stdinFD)
					if err != nil {
						continue
					}
					_ = c.ResizeContext(ctx, uint16(cols), uint16(rows))
				}
			}
		}()
	}

	// Reader: PTY stream -> stdout.
	stream, err := c.Stream(ctx)
	if err != nil {
		cancel()
		wg.Wait()
		return err
	}
	defer stream.Close()

	readErrCh := make(chan error, 1)
	wg.Add(1)
	go func() {
		defer wg.Done()
		_, err := io.Copy(stdout, stream)
		readErrCh <- err
	}()

	// Writer: stdin -> /pty/input, watching for the detach chord.
	writeErrCh := make(chan error, 1)
	detachCh := make(chan struct{})
	wg.Add(1)
	go func() {
		defer wg.Done()
		writeErrCh <- c.pumpStdin(ctx, stdin, chord, detachCh)
	}()

	var retErr error
	select {
	case <-ctx.Done():
	case err := <-readErrCh:
		if err != nil && !errors.Is(err, io.EOF) && !errors.Is(err, context.Canceled) {
			retErr = err
		}
	case err := <-writeErrCh:
		if err != nil && !errors.Is(err, io.EOF) && !errors.Is(err, context.Canceled) {
			retErr = err
		}
	case <-detachCh:
		// Clean detach.
	}
	cancel()
	wg.Wait()
	return retErr
}

// pumpStdin reads from stdin one byte at a time, watching for the
// detach chord. Non-chord bytes flow to /pty/input in small
// batches (up to 64 bytes per POST).
func (c *Client) pumpStdin(ctx context.Context, stdin *os.File, chord []byte, detachCh chan<- struct{}) error {
	buf := make([]byte, 64)

	// State machine: if the last byte matched chord[0], the next
	// byte either detaches (if chord[1]) or flushes the saved
	// prefix + current byte.
	var pending []byte // usually empty; holds chord[0] when seen

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}
		n, err := stdin.Read(buf)
		if n > 0 {
			data := append([]byte{}, pending...)
			pending = pending[:0]
			for i := 0; i < n; i++ {
				b := buf[i]
				if len(chord) == 2 {
					if len(pending) == 0 && b == chord[0] {
						// Defer: could be a chord.
						pending = append(pending, b)
						continue
					}
					if len(pending) == 1 {
						if b == chord[1] {
							// Detach! Don't send anything
							// accumulated after the chord prefix.
							close(detachCh)
							return nil
						}
						// Not a chord — emit the saved prefix
						// plus this byte.
						data = append(data, pending...)
						pending = pending[:0]
					}
				}
				data = append(data, b)
			}
			if len(data) > 0 {
				if err := c.WriteContext(ctx, data); err != nil {
					return err
				}
			}
		}
		if err != nil {
			return err
		}
	}
}

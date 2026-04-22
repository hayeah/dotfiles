package supervisor

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/creack/pty"
	"golang.org/x/term"
)

// openPTYPair opens a PTY master/slave pair, puts the slave into
// raw mode so Read doesn't block on line discipline, and returns
// (master, slave). t.Cleanup handles close.
func openPTYPair(t *testing.T) (*os.File, *os.File) {
	t.Helper()
	master, slave, err := pty.Open()
	if err != nil {
		t.Fatalf("pty.Open: %v", err)
	}
	t.Cleanup(func() {
		_ = master.Close()
		_ = slave.Close()
	})
	if err := pty.Setsize(master, &pty.Winsize{Cols: 80, Rows: 24}); err != nil {
		t.Fatalf("pty.Setsize: %v", err)
	}
	// MakeRaw returns the old state; we don't restore (process
	// exits with the test), just want reads to fire per-byte
	// without waiting for newlines.
	if _, err := term.MakeRaw(int(slave.Fd())); err != nil {
		t.Fatalf("term.MakeRaw: %v", err)
	}
	return master, slave
}

// TestLibghosttyPTYFeedCapture writes bytes into the slave end of a
// PTY pair, lets LibghosttyPTY's reader goroutine feed the
// emulator, and asserts Capture() returns the text.
func TestLibghosttyPTYFeedCapture(t *testing.T) {
	master, slave := openPTYPair(t)

	p, err := NewLibghosttyPTY(master, 80, 24)
	if err != nil {
		t.Fatalf("NewLibghosttyPTY: %v", err)
	}
	t.Cleanup(func() { _ = p.Close() })

	// Write to slave -> emulator sees it via master reader.
	if _, err := slave.Write([]byte("hello pty\r\n")); err != nil {
		t.Fatalf("slave.Write: %v", err)
	}

	// Give the dispatcher a beat.
	deadline := time.Now().Add(2 * time.Second)
	var got string
	for time.Now().Before(deadline) {
		got, err = p.Capture(0, false)
		if err != nil {
			t.Fatalf("Capture: %v", err)
		}
		if strings.Contains(got, "hello pty") {
			return
		}
		time.Sleep(25 * time.Millisecond)
	}
	t.Errorf("emulator never saw 'hello pty'; Capture returned:\n%q", got)
}

// TestLibghosttyPTYResizePropagates asserts Resize updates both the
// kernel winsize and the emulator grid.
func TestLibghosttyPTYResizePropagates(t *testing.T) {
	master, _ := openPTYPair(t)
	p, err := NewLibghosttyPTY(master, 80, 24)
	if err != nil {
		t.Fatalf("NewLibghosttyPTY: %v", err)
	}
	t.Cleanup(func() { _ = p.Close() })

	if err := p.Resize(120, 40); err != nil {
		t.Fatalf("Resize: %v", err)
	}
	ws, err := pty.GetsizeFull(master)
	if err != nil {
		t.Fatalf("GetsizeFull: %v", err)
	}
	if ws.Cols != 120 || ws.Rows != 40 {
		t.Errorf("kernel winsize = %dx%d, want 120x40", ws.Cols, ws.Rows)
	}
	cols, rows := p.Size()
	if cols != 120 || rows != 40 {
		t.Errorf("PTY.Size = %dx%d, want 120x40", cols, rows)
	}
}

// TestLibghosttyPTYSendKeys verifies that SendKeys for a known key
// ("Enter") writes to the master (which shows up on the slave) and
// that an unknown name falls through as literal bytes.
func TestLibghosttyPTYSendKeys(t *testing.T) {
	master, slave := openPTYPair(t)
	p, err := NewLibghosttyPTY(master, 80, 24)
	if err != nil {
		t.Fatalf("NewLibghosttyPTY: %v", err)
	}
	t.Cleanup(func() { _ = p.Close() })

	if err := p.SendKeys("hello", "Enter"); err != nil {
		t.Fatalf("SendKeys: %v", err)
	}

	// Read from slave to see what the master sent (echo the user's
	// input — from the child process perspective).
	_ = slave.SetReadDeadline(time.Now().Add(2 * time.Second))
	buf := make([]byte, 64)
	n, err := slave.Read(buf)
	if err != nil {
		t.Fatalf("slave.Read: %v", err)
	}
	got := string(buf[:n])
	if !strings.Contains(got, "hello") {
		t.Errorf("slave did not receive literal 'hello'; got %q", got)
	}
	// "Enter" as encoded by libghostty should include a \r somewhere.
	if !bytes.ContainsAny(buf[:n], "\r\n") {
		t.Errorf("slave did not receive Enter bytes; got %q", got)
	}
}

// TestLibghosttyPTYStreamDelivers drives /pty/stream end-to-end:
// subscribe via HTTP, write into slave, assert the stream emits the
// snapshot then the live bytes.
func TestLibghosttyPTYStreamDelivers(t *testing.T) {
	master, slave := openPTYPair(t)
	p, err := NewLibghosttyPTY(master, 80, 24)
	if err != nil {
		t.Fatalf("NewLibghosttyPTY: %v", err)
	}
	t.Cleanup(func() { _ = p.Close() })

	// Prime the emulator so snapshot has non-empty content.
	_, _ = slave.Write([]byte("preload\r\n"))
	time.Sleep(100 * time.Millisecond)

	mux := http.NewServeMux()
	p.RegisterRoutes(mux)
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	t.Cleanup(cancel)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, srv.URL+"/pty/stream", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("stream GET: %v", err)
	}
	t.Cleanup(func() { _ = resp.Body.Close() })

	// Read the first chunk (should contain the snapshot).
	first := make([]byte, 8192)
	n, err := resp.Body.Read(first)
	if err != nil && err != io.EOF {
		t.Fatalf("read snapshot: %v", err)
	}
	snap := string(first[:n])
	if !strings.Contains(snap, "preload") {
		t.Errorf("snapshot did not contain 'preload'; got %q", snap)
	}

	// Write live bytes; they should arrive on the stream.
	_, _ = slave.Write([]byte("live-data-xyz\r\n"))

	// Drain the stream in a goroutine; wait on either the live
	// data showing up or the test timeout.
	type chunk struct {
		data []byte
		err  error
	}
	out := make(chan chunk, 8)
	go func() {
		buf := make([]byte, 4096)
		for {
			n, err := resp.Body.Read(buf)
			if n > 0 {
				out <- chunk{data: append([]byte{}, buf[:n]...)}
			}
			if err != nil {
				out <- chunk{err: err}
				return
			}
		}
	}()

	var got strings.Builder
	got.WriteString(snap)
	timeout := time.After(2 * time.Second)
	for {
		select {
		case c := <-out:
			if len(c.data) > 0 {
				got.Write(c.data)
				if strings.Contains(got.String(), "live-data-xyz") {
					return
				}
			}
			if c.err != nil {
				t.Fatalf("stream closed before live data arrived; err=%v; got:\n%q", c.err, got.String())
			}
		case <-timeout:
			t.Fatalf("stream never saw 'live-data-xyz' within 2s; got:\n%q", got.String())
		}
	}
}

// TestLibghosttyPTYInputRoute verifies POST /pty/input sends bytes
// to the master (visible on the slave end).
func TestLibghosttyPTYInputRoute(t *testing.T) {
	master, slave := openPTYPair(t)
	p, err := NewLibghosttyPTY(master, 80, 24)
	if err != nil {
		t.Fatalf("NewLibghosttyPTY: %v", err)
	}
	t.Cleanup(func() { _ = p.Close() })

	mux := http.NewServeMux()
	p.RegisterRoutes(mux)
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)

	resp, err := http.Post(srv.URL+"/pty/input", "application/octet-stream", bytes.NewReader([]byte("via-http")))
	if err != nil {
		t.Fatalf("POST /pty/input: %v", err)
	}
	_ = resp.Body.Close()
	if resp.StatusCode != http.StatusNoContent {
		t.Errorf("status = %d, want 204", resp.StatusCode)
	}

	_ = slave.SetReadDeadline(time.Now().Add(1 * time.Second))
	buf := make([]byte, 32)
	n, err := slave.Read(buf)
	if err != nil {
		t.Fatalf("slave.Read: %v", err)
	}
	if string(buf[:n]) != "via-http" {
		t.Errorf("slave got %q, want %q", string(buf[:n]), "via-http")
	}
}

// TestLibghosttyPTYResizeRoute verifies POST /pty/resize with
// JSON body updates the kernel winsize.
func TestLibghosttyPTYResizeRoute(t *testing.T) {
	master, _ := openPTYPair(t)
	p, err := NewLibghosttyPTY(master, 80, 24)
	if err != nil {
		t.Fatalf("NewLibghosttyPTY: %v", err)
	}
	t.Cleanup(func() { _ = p.Close() })

	mux := http.NewServeMux()
	p.RegisterRoutes(mux)
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)

	body, _ := json.Marshal(map[string]uint16{"cols": 100, "rows": 30})
	resp, err := http.Post(srv.URL+"/pty/resize", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("POST /pty/resize: %v", err)
	}
	_ = resp.Body.Close()
	if resp.StatusCode != http.StatusNoContent {
		t.Errorf("status = %d, want 204", resp.StatusCode)
	}

	ws, err := pty.GetsizeFull(master)
	if err != nil {
		t.Fatalf("GetsizeFull: %v", err)
	}
	if ws.Cols != 100 || ws.Rows != 30 {
		t.Errorf("kernel winsize = %dx%d, want 100x30", ws.Cols, ws.Rows)
	}
}

// TestRunnerRegistersLibghosttyRoutes checks that Runner.Run picks
// up the RegisterRoutes interface and mounts /pty/* when the
// configured PTY is a LibghosttyPTY.
func TestRunnerRegistersLibghosttyRoutes(t *testing.T) {
	master, _ := openPTYPair(t)
	p, err := NewLibghosttyPTY(master, 80, 24)
	if err != nil {
		t.Fatalf("NewLibghosttyPTY: %v", err)
	}

	dir := shortTempDir(t)

	svc := serviceFunc(func(ctx context.Context, super Supervisor) error {
		_ = super.UpdateState(map[string]string{"state": "running"})
		<-ctx.Done()
		return ctx.Err()
	})

	runner := New(SupervisorConfig{StateDir: dir, Key: "demo", Service: svc, PTY: p})

	ctx, cancel := context.WithCancel(context.Background())
	runExit := make(chan error, 1)
	go func() { runExit <- runner.Run(ctx) }()
	t.Cleanup(func() {
		cancel()
		select {
		case <-runExit:
		case <-time.After(2 * time.Second):
			t.Error("runner did not exit within 2s of cancel")
		}
	})

	// Wait for rpc.sock to appear.
	sockPath := filepath.Join(dir, "demo", "rpc.sock")
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(sockPath); err == nil {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}

	client := &http.Client{
		Transport: &http.Transport{
			DialContext: func(_ context.Context, _, _ string) (net.Conn, error) {
				return net.Dial("unix", sockPath)
			},
		},
		Timeout: 2 * time.Second,
	}

	resp, err := client.Get("http://unix/pty/snapshot")
	if err != nil {
		t.Fatalf("GET /pty/snapshot: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Errorf("status = %d, want 200 (route should be mounted)", resp.StatusCode)
	}
}

// unused helper that documents the dep; keeps go imports happy in
// case we add a PTY spawn test later.
var _ = exec.Command

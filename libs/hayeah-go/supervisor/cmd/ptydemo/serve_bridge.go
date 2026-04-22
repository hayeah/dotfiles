package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"path/filepath"

	"github.com/coder/websocket"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor/ptyclient"
)

// handleEvents proxies a session's /events SSE stream from its
// rpc.sock to the HTTP client. The transport lets the web UI keep
// one event subscription per session without having to dial the
// unix socket itself (browsers can't).
func (s *serveState) handleEvents(w http.ResponseWriter, r *http.Request) {
	key := r.PathValue("key")
	if key == "" {
		http.Error(w, "missing session key", http.StatusBadRequest)
		return
	}
	sockPath := filepath.Join(s.stateDir, key, "rpc.sock")
	client := ptyclient.NewClient(sockPath)
	defer client.Close()

	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, "http://unix/events", nil)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	resp, err := client.HTTPClient().Do(req)
	if err != nil {
		http.Error(w, "upstream: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		http.Error(w, "upstream status "+resp.Status, http.StatusBadGateway)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}
	flusher.Flush()

	buf := make([]byte, 4096)
	for {
		n, rerr := resp.Body.Read(buf)
		if n > 0 {
			if _, werr := w.Write(buf[:n]); werr != nil {
				return
			}
			flusher.Flush()
		}
		if rerr != nil {
			return
		}
	}
}

// attachMessage is the JSON payload for non-byte WS messages. Today:
//
//	{type:"resize", cols:N, rows:N}
//
// We pick a tagged-envelope shape because binary frames are PTY
// bytes — there is no room for metadata alongside them, and
// splitting the sidebands off into text frames keeps the parser
// trivial on both sides.
type attachMessage struct {
	Type string `json:"type"`
	Cols uint16 `json:"cols,omitempty"`
	Rows uint16 `json:"rows,omitempty"`
}

// handleAttach is the browser-facing WebSocket bridge. Binary
// frames are raw PTY bytes in both directions (server→client is
// snapshot-then-live, matching /pty/stream; client→server is raw
// input going into /pty/input). Text frames carry a JSON envelope
// — today just {type:"resize", cols, rows}.
func (s *serveState) handleAttach(w http.ResponseWriter, r *http.Request) {
	key := r.PathValue("key")
	if key == "" {
		http.Error(w, "missing session key", http.StatusBadRequest)
		return
	}
	sockPath := filepath.Join(s.stateDir, key, "rpc.sock")
	client := ptyclient.NewClient(sockPath)
	defer client.Close()

	conn, err := websocket.Accept(w, r, &websocket.AcceptOptions{
		// Browser origin checks are handled by the reverse proxy
		// (devport/vite) in dev, and by same-origin in prod. This
		// demo binary is never exposed to untrusted origins.
		InsecureSkipVerify: true,
	})
	if err != nil {
		// websocket.Accept has already written a response.
		return
	}
	defer conn.Close(websocket.StatusNormalClosure, "bye")

	ctx, cancel := context.WithCancel(r.Context())
	defer cancel()

	// Pump 1: PTY stream → WS binary frames.
	streamBody, err := client.Stream(ctx)
	if err != nil {
		_ = conn.Close(websocket.StatusInternalError, fmt.Sprintf("stream: %v", err))
		return
	}
	defer streamBody.Close()

	readErrCh := make(chan error, 1)
	go func() {
		readErrCh <- pumpStreamToWS(ctx, conn, streamBody)
	}()

	// Pump 2: WS frames → /pty/{input,resize}.
	writeErrCh := make(chan error, 1)
	go func() {
		writeErrCh <- pumpWSToPTY(ctx, conn, client)
	}()

	// Any of the three cases is a clean teardown — the deferred
	// conn.Close and cancel handle the rest. Errors are swallowed;
	// connection loss is not exceptional for an attach.
	select {
	case <-r.Context().Done():
	case <-readErrCh:
	case <-writeErrCh:
	}
}

// pumpStreamToWS reads bytes from the PTY stream and sends them as
// binary WS frames. Returns on EOF or any read/write error.
func pumpStreamToWS(ctx context.Context, conn *websocket.Conn, stream io.Reader) error {
	buf := make([]byte, 4096)
	for {
		n, err := stream.Read(buf)
		if n > 0 {
			if werr := conn.Write(ctx, websocket.MessageBinary, buf[:n]); werr != nil {
				return werr
			}
		}
		if err != nil {
			return err
		}
	}
}

// pumpWSToPTY reads WS frames and dispatches:
//
//   - binary frames → POST /pty/input (raw bytes; user keystrokes
//     and paste)
//   - text frames → JSON-decoded attachMessage; today only
//     {type:"resize", cols, rows} is recognized. Unknown types are
//     ignored (forward-compatible for future {type:"ping"}, etc).
func pumpWSToPTY(ctx context.Context, conn *websocket.Conn, client *ptyclient.Client) error {
	for {
		typ, data, err := conn.Read(ctx)
		if err != nil {
			return err
		}
		switch typ {
		case websocket.MessageBinary:
			if len(data) == 0 {
				continue
			}
			if werr := client.WriteContext(ctx, data); werr != nil {
				return werr
			}
		case websocket.MessageText:
			var msg attachMessage
			if jerr := json.Unmarshal(data, &msg); jerr != nil {
				continue
			}
			switch msg.Type {
			case "resize":
				if msg.Cols == 0 || msg.Rows == 0 {
					continue
				}
				_ = client.ResizeContext(ctx, msg.Cols, msg.Rows)
			default:
				// Unknown; ignore for forward compatibility.
			}
		}
	}
}


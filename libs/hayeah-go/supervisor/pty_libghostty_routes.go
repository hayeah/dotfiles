package supervisor

import (
	"encoding/json"
	"io"
	"net/http"
	"strconv"
)

// handleInput reads the request body and writes it to the PTY
// master. Used by /pty/input POSTs — the body is raw bytes (any
// content type).
func (p *LibghosttyPTY) handleInput(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	defer r.Body.Close()
	data, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "read body: "+err.Error(), http.StatusBadRequest)
		return
	}
	if err := p.Write(data); err != nil {
		http.Error(w, "write pty: "+err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// handleResize accepts JSON {cols, rows} and updates both the
// kernel winsize and the emulator grid.
func (p *LibghosttyPTY) handleResize(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var body struct {
		Cols uint16 `json:"cols"`
		Rows uint16 `json:"rows"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, "bad body: "+err.Error(), http.StatusBadRequest)
		return
	}
	if body.Cols == 0 || body.Rows == 0 {
		http.Error(w, "cols and rows must be positive", http.StatusBadRequest)
		return
	}
	if err := p.Resize(body.Cols, body.Rows); err != nil {
		http.Error(w, "resize: "+err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// handleSendKeys accepts JSON {keys: [...]} and dispatches each
// through SendKeys. Bodies where an entry is an unknown key name
// flow through as literal bytes (matching tmux's behavior).
func (p *LibghosttyPTY) handleSendKeys(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var body struct {
		Keys []string `json:"keys"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, "bad body: "+err.Error(), http.StatusBadRequest)
		return
	}
	if err := p.SendKeys(body.Keys...); err != nil {
		http.Error(w, "send keys: "+err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// handleStream serves the chunked binary stream that drives a
// browser or client attach. First chunk is the ANSI snapshot
// (DumpVTFull); subsequent chunks are live PTY bytes as they flow
// from the child.
func (p *LibghosttyPTY) handleStream(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	// Subscribe BEFORE taking the snapshot, so any bytes that
	// arrive between snapshot and first live delivery are queued
	// on the channel rather than lost. The dispatcher serializes
	// subscribe with feed, so no bytes slip between them.
	ch, cancel := p.subscribe()
	defer cancel()

	snap, err := p.Snapshot()
	if err != nil {
		http.Error(w, "snapshot: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.WriteHeader(http.StatusOK)

	if len(snap) > 0 {
		if _, err := w.Write(snap); err != nil {
			return
		}
		flusher.Flush()
	}

	for {
		select {
		case <-r.Context().Done():
			return
		case chunk, ok := <-ch:
			if !ok {
				return
			}
			if _, err := w.Write(chunk); err != nil {
				return
			}
			flusher.Flush()
		}
	}
}

// handleSnapshot returns a one-shot screen dump. Query params:
//
//	?lines=N     (advisory — currently ignored)
//	?escapes=0|1 (0 = plain text, 1 = ANSI with colors)
func (p *LibghosttyPTY) handleSnapshot(w http.ResponseWriter, r *http.Request) {
	linesStr := r.URL.Query().Get("lines")
	lines := 0
	if linesStr != "" {
		n, err := strconv.Atoi(linesStr)
		if err != nil {
			http.Error(w, "bad lines", http.StatusBadRequest)
			return
		}
		lines = n
	}
	withEscapes := r.URL.Query().Get("escapes") == "1"
	out, err := p.Capture(lines, withEscapes)
	if err != nil {
		http.Error(w, "capture: "+err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write([]byte(out))
}

// handleScrollback returns scrollback + screen as plain text.
// Query param: ?lines=N (advisory — currently ignored).
func (p *LibghosttyPTY) handleScrollback(w http.ResponseWriter, r *http.Request) {
	linesStr := r.URL.Query().Get("lines")
	lines := 0
	if linesStr != "" {
		n, err := strconv.Atoi(linesStr)
		if err != nil {
			http.Error(w, "bad lines", http.StatusBadRequest)
			return
		}
		lines = n
	}
	out, err := p.ScrollbackText(lines)
	if err != nil {
		http.Error(w, "scrollback: "+err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write([]byte(out))
}

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
)

// cmdServe is the API-only HTTP server for the demo.
//
// Routes (all under /api/ when devport proxies; naked paths when
// hitting ptydemo directly):
//
//	GET  /api/sessions                  — JSONL of all known sessions
//	GET  /api/sessions/{key}/state      — state.json for one session
//	GET  /api/sessions/{key}/attach     — WebSocket bridge (TODO)
//	GET  /api/healthz                   — health probe for devport
//
// devportv3 owns the proxy / frontend orchestration; ptydemo never
// serves HTML.
func cmdServe(args []string) error {
	fs := flag.NewFlagSet("serve", flag.ContinueOnError)
	port := fs.Int("port", 0, "TCP port to listen on (0 = pick one)")
	addr := fs.String("addr", "127.0.0.1", "interface to bind")
	stateDir := fs.String("state-dir", defaultStateDir(), "session state directory")
	prefix := fs.String("prefix", "", "path prefix devport strips before proxying (usually \"/api\"; leave blank when talking directly)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *port == 0 {
		return fmt.Errorf("--port is required")
	}
	if err := os.MkdirAll(*stateDir, 0o755); err != nil {
		return fmt.Errorf("mkdir state-dir: %w", err)
	}

	store := supervisor.NewStore(*stateDir)
	srv := &serveState{store: store, stateDir: *stateDir}

	mux := http.NewServeMux()
	register(mux, *prefix, "/sessions", srv.handleSessions)
	register(mux, *prefix, "/sessions/{key}/state", srv.handleState)
	register(mux, *prefix, "/healthz", srv.handleHealth)

	listenAddr := fmt.Sprintf("%s:%d", *addr, *port)
	fmt.Fprintf(os.Stderr, "ptydemo: listening on http://%s (state-dir=%s)\n", listenAddr, *stateDir)
	return http.ListenAndServe(listenAddr, mux)
}

// register mounts a handler at both the prefixed and unprefixed
// path so the same binary works whether it's behind a proxy
// (strip_prefix=false keeps /api/) or hit directly (bare path).
// Using both means a dev can hit http://127.0.0.1:<port>/sessions
// for direct probing even while devport proxies /api/sessions.
func register(mux *http.ServeMux, prefix, path string, h http.HandlerFunc) {
	mux.HandleFunc(path, h)
	if prefix != "" {
		mux.HandleFunc(prefix+path, h)
	}
}

type serveState struct {
	store    *supervisor.Store
	stateDir string
}

// handleSessions returns JSON {sessions: [...]} — each entry is a
// StateFile. Sessions are walked off the filesystem; no process
// interaction needed.
func (s *serveState) handleSessions(w http.ResponseWriter, r *http.Request) {
	states, err := s.store.List()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	// Also mark whether each session is alive (flock held).
	type entry struct {
		*supervisor.StateFile
		Alive bool `json:"alive"`
	}
	out := struct {
		Sessions []entry `json:"sessions"`
	}{Sessions: make([]entry, 0, len(states))}
	for _, st := range states {
		out.Sessions = append(out.Sessions, entry{
			StateFile: st,
			Alive:     s.store.IsAlive(st.Supervisor.Key),
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}

// handleState returns the state.json for one session.
func (s *serveState) handleState(w http.ResponseWriter, r *http.Request) {
	key := r.PathValue("key")
	if key == "" {
		http.Error(w, "missing session key", http.StatusBadRequest)
		return
	}
	st, err := s.store.Load(key)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(st)
}

func (s *serveState) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":         true,
		"state_dir":  s.stateDir,
		"started_at": time.Now(),
	})
}

var _ = filepath.Join // retained for future subcommands

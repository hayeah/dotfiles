package supervisor

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
)

// ListenSocket starts a unix domain socket HTTP server that serves SSE
// events from the EventBus plus any custom handlers.
//
// macOS caveat: unix socket paths must be < 104 bytes.
func ListenSocket(path string, bus *EventBus, handlers map[string]http.HandlerFunc) (io.Closer, error) {
	// Remove stale socket if it exists
	os.Remove(path)

	listener, err := net.Listen("unix", path)
	if err != nil {
		return nil, fmt.Errorf("listen unix %q: %w", path, err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/events", sseHandler(bus))
	for pattern, handler := range handlers {
		mux.HandleFunc(pattern, handler)
	}

	server := &http.Server{Handler: mux}
	go server.Serve(listener)

	return &socketCloser{server: server, listener: listener, path: path}, nil
}

func sseHandler(bus *EventBus) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "streaming not supported", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
		flusher.Flush()

		ch, unsub := bus.Subscribe()
		defer unsub()

		for {
			select {
			case ev, ok := <-ch:
				if !ok {
					return
				}
				fmt.Fprintf(w, "event: %s\ndata: %s\n\n", ev.Type, string(ev.Data))
				flusher.Flush()
			case <-r.Context().Done():
				return
			}
		}
	}
}

type socketCloser struct {
	server   *http.Server
	listener net.Listener
	path     string
}

func (s *socketCloser) Close() error {
	s.server.Close()
	s.listener.Close()
	os.Remove(s.path)
	return nil
}

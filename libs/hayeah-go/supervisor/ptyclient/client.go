// Package ptyclient is the client-side companion to the
// supervisor's /pty/* HTTP routes. It speaks unix-socket HTTP to a
// running supervisor and exposes a small API matching the PTY
// interface (Write/SendKeys/Capture/Resize) plus Stream() for
// long-running attaches and AttachStdio() for terminal clients.
//
// Lives in its own sub-package so consumers that only need the
// library's plugin/service scaffolding don't transitively pull in
// raw-mode tty handling (AttachStdio imports golang.org/x/term).
package ptyclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
)

// Client speaks to a supervisor via its rpc.sock. Construct with
// NewClient; call Close when done (closes the underlying HTTP
// transport's idle connections).
type Client struct {
	socketPath string
	httpClient *http.Client
}

// NewClient dials the given unix socket path for every request.
func NewClient(socketPath string) *Client {
	return &Client{
		socketPath: socketPath,
		httpClient: &http.Client{
			Transport: &http.Transport{
				DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
					var d net.Dialer
					return d.DialContext(ctx, "unix", socketPath)
				},
			},
		},
	}
}

// Close closes idle connections. The client remains usable — a
// subsequent request will redial.
func (c *Client) Close() error {
	c.httpClient.CloseIdleConnections()
	return nil
}

// HTTPClient exposes the underlying http.Client for callers that
// need to make ad-hoc requests against the same rpc.sock (e.g.
// agentboss's lease endpoints).
func (c *Client) HTTPClient() *http.Client { return c.httpClient }

// url builds an http://unix URL for a path.
func (c *Client) url(path string) string {
	return (&url.URL{Scheme: "http", Host: "unix", Path: path}).String()
}

// Write sends raw bytes to POST /pty/input.
func (c *Client) Write(data []byte) error {
	return c.WriteContext(context.Background(), data)
}

// WriteContext is like Write but cancellable.
func (c *Client) WriteContext(ctx context.Context, data []byte) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url("/pty/input"), bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/octet-stream")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return checkStatus(resp)
}

// Resize posts JSON {cols, rows} to /pty/resize.
func (c *Client) Resize(cols, rows uint16) error {
	return c.ResizeContext(context.Background(), cols, rows)
}

// ResizeContext is like Resize but cancellable.
func (c *Client) ResizeContext(ctx context.Context, cols, rows uint16) error {
	body, _ := json.Marshal(map[string]uint16{"cols": cols, "rows": rows})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url("/pty/resize"), bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return checkStatus(resp)
}

// SendKeys posts JSON {keys:[...]} to /pty/send-keys.
func (c *Client) SendKeys(keys ...string) error {
	return c.SendKeysContext(context.Background(), keys...)
}

// SendKeysContext is like SendKeys but cancellable.
func (c *Client) SendKeysContext(ctx context.Context, keys ...string) error {
	body, _ := json.Marshal(map[string][]string{"keys": keys})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url("/pty/send-keys"), bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return checkStatus(resp)
}

// Capture returns a one-shot screen dump from /pty/snapshot.
func (c *Client) Capture(lines int, withEscapes bool) (string, error) {
	return c.CaptureContext(context.Background(), lines, withEscapes)
}

// CaptureContext is like Capture but cancellable.
func (c *Client) CaptureContext(ctx context.Context, lines int, withEscapes bool) (string, error) {
	u := c.url("/pty/snapshot")
	q := url.Values{}
	if lines > 0 {
		q.Set("lines", fmt.Sprintf("%d", lines))
	}
	if withEscapes {
		q.Set("escapes", "1")
	}
	if len(q) > 0 {
		u += "?" + q.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return "", err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if err := checkStatus(resp); err != nil {
		return "", err
	}
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// Stream opens /pty/stream and returns the chunked body. Caller
// Close()s to disconnect. The first chunk is an ANSI snapshot;
// subsequent bytes are live.
func (c *Client) Stream(ctx context.Context) (io.ReadCloser, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.url("/pty/stream"), nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		defer resp.Body.Close()
		return nil, fmt.Errorf("stream status %d", resp.StatusCode)
	}
	return resp.Body, nil
}

func checkStatus(resp *http.Response) error {
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("%s: %s", resp.Status, string(body))
	}
	return nil
}

import type { SessionSummary } from "./types";

// AttachStream is a bidirectional byte pipe. Both impls (mock +
// live) return one per `attach(sessionKey)` call. It's the thin
// contract ghostty-web needs: bytes flow both directions, plus a
// resize signal toward the backend.
export interface AttachStream {
  // onBytes is invoked as the backend produces output. Delivered
  // in chunks; consumer doesn't need to re-parse boundaries.
  onBytes(fn: (bytes: Uint8Array) => void): () => void;

  // send writes user input to the backend PTY master.
  send(bytes: Uint8Array): void;

  // resize informs the backend of a new terminal size.
  resize(cols: number, rows: number): void;

  // close tears down the stream. Safe to call multiple times.
  close(): void;
}

// DataSource is the only API the views see. MockDataSource (for
// /preview) and LiveDataSource (for the real app) both implement
// it. Views never import from mock.ts or anything backend-specific.
export interface DataSource {
  sessions: SessionSummary[];
  attach(sessionKey: string): AttachStream;

  // createSession spawns a new session with the given shell command
  // (e.g. "bash -l"). Mock returns immediately with a fake summary;
  // Live POSTs to /api/sessions and waits for the supervisor's
  // initial state to be published.
  createSession(cmd: string): Promise<SessionSummary>;
}

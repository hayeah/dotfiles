import { observer } from "mobx-react-lite";
import { useState } from "react";
import type { SessionSummary } from "../data/types";

interface Props {
  sessions: SessionSummary[];
  activeKey: string | null;
  onSelect(key: string): void;
  onCreate?(cmd: string): Promise<SessionSummary>;
}

// SessionSidebar is the left column: one tab per known session.
// Click a tab to focus its terminal in the main pane. Tabs show
// liveness + state at a glance.
export const SessionSidebar = observer(function SessionSidebar({
  sessions,
  activeKey,
  onSelect,
  onCreate,
}: Props) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="text-sm font-semibold">Sessions</div>
        <div className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {sessions.length}
        </div>
      </div>
      {onCreate && <NewSessionForm onCreate={onCreate} onCreated={(s) => onSelect(s.key)} />}
      <nav className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 && (
          <div className="px-2 py-4 text-xs text-muted-foreground">No sessions yet.</div>
        )}
        {sessions.map((s) => (
          <SessionTab
            key={s.key}
            session={s}
            active={s.key === activeKey}
            onClick={() => onSelect(s.key)}
          />
        ))}
      </nav>
      <footer className="border-t border-border px-4 py-2 text-[10px] uppercase tracking-wide text-muted-foreground">
        ptydemo
      </footer>
    </aside>
  );
});

function NewSessionForm({
  onCreate,
  onCreated,
}: {
  onCreate(cmd: string): Promise<SessionSummary>;
  onCreated(s: SessionSummary): void;
}) {
  const [cmd, setCmd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const s = await onCreate(cmd || "bash -l");
      setCmd("");
      onCreated(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-1 border-b border-border bg-muted/30 px-3 py-2"
    >
      <div className="flex gap-1">
        <input
          type="text"
          value={cmd}
          onChange={(e) => setCmd(e.target.value)}
          placeholder="bash -l"
          disabled={busy}
          className="min-w-0 flex-1 rounded-md border border-input bg-background px-2 py-1 font-mono text-xs focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 disabled:opacity-50"
          aria-label="Command to run"
        />
        <button
          type="submit"
          disabled={busy}
          className="shrink-0 rounded-md bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {busy ? "…" : "+"}
        </button>
      </div>
      {error && <div className="text-[10px] text-destructive">{error}</div>}
    </form>
  );
}

function SessionTab({
  session,
  active,
  onClick,
}: {
  session: SessionSummary;
  active: boolean;
  onClick: () => void;
}) {
  const tone =
    session.state === "running"
      ? "bg-green-500"
      : session.state === "starting"
        ? "bg-amber-500"
        : session.state === "exited"
          ? "bg-muted-foreground/40"
          : "bg-muted-foreground/60";

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "group mb-1 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left transition-colors",
        active
          ? "bg-primary/10 text-foreground"
          : "text-foreground/80 hover:bg-muted",
      ].join(" ")}
    >
      <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${tone}`} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{session.key}</span>
        <span className="block truncate font-mono text-xs text-muted-foreground">
          {session.cmd}
        </span>
      </span>
    </button>
  );
}

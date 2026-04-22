import { observer } from "mobx-react-lite";
import { useEffect, useRef } from "react";
import type { DataSource } from "../data/source";
import type { SessionSummary } from "../data/types";

interface Props {
  ds: DataSource;
  session: SessionSummary;
}

// TerminalPane renders a single session's PTY in the main column.
// The header shows session metadata; the body mounts ghostty-web
// into a div and subscribes to the AttachStream returned by the
// data source. When the session key changes (user clicks a
// different sidebar tab), the old terminal is torn down and a new
// one mounts — the component key below forces a remount.
export const TerminalPane = observer(function TerminalPane({ ds, session }: Props) {
  return (
    <>
      <header className="flex items-center justify-between border-b border-border bg-card px-6 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <div className="truncate text-base font-semibold">{session.key}</div>
            <StateBadge state={session.state} />
          </div>
          <div className="truncate font-mono text-xs text-muted-foreground">
            {session.cmd}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {session.pid != null && <span>pid {session.pid}</span>}
          <span>·</span>
          <span>started {timeAgo(session.startedAt)}</span>
        </div>
      </header>
      <div className="flex flex-1 flex-col bg-[#0f1018] p-0">
        <TerminalHost
          key={session.key}
          onReady={(mount) => mountTerminal(mount, ds, session.key)}
        />
      </div>
    </>
  );
});

function StateBadge({ state }: { state: SessionSummary["state"] }) {
  const tone =
    state === "running"
      ? "bg-green-500/15 text-green-400 ring-green-500/30"
      : state === "starting"
        ? "bg-amber-500/15 text-amber-400 ring-amber-500/30"
        : state === "exited"
          ? "bg-muted-foreground/10 text-muted-foreground ring-muted-foreground/20"
          : "bg-muted-foreground/10 text-muted-foreground ring-muted-foreground/20";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ${tone}`}>
      {state}
    </span>
  );
}

function TerminalHost({
  onReady,
}: {
  onReady: (mount: HTMLDivElement) => () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const cleanup = onReady(ref.current);
    return cleanup;
  }, [onReady]);
  return <div ref={ref} className="h-full w-full min-h-0" />;
}

// mountTerminal lazily imports ghostty-web, initializes the WASM
// runtime once, constructs a Terminal, and wires up the
// bidirectional AttachStream. Returns a disposer that the effect
// uses on unmount.
function mountTerminal(mount: HTMLDivElement, ds: DataSource, sessionKey: string) {
  let disposed = false;
  const teardown: Array<() => void> = [];

  (async () => {
    const { init, Terminal } = await import("ghostty-web");
    if (disposed) return;
    await init();
    if (disposed) return;

    const term = new Terminal({
      fontSize: 13,
      theme: {
        background: "#0f1018",
        foreground: "#d4d4d8",
      },
    });
    term.open(mount);
    teardown.push(() => term.dispose?.());

    const stream = ds.attach(sessionKey);
    teardown.push(() => stream.close());

    const unsubscribe = stream.onBytes((bytes) => {
      term.write(bytes);
    });
    teardown.push(unsubscribe);

    const onDataDispose = term.onData?.((data: string) => {
      stream.send(new TextEncoder().encode(data));
    });
    if (onDataDispose) teardown.push(() => onDataDispose.dispose?.());
  })().catch((err) => {
    // In preview we don't have a real backend; surface the error
    // to the mount so it's obvious something failed.
    mount.innerText = `terminal failed: ${err?.message ?? String(err)}`;
  });

  return () => {
    disposed = true;
    for (const fn of teardown) {
      try {
        fn();
      } catch {
        // best-effort
      }
    }
  };
}

function timeAgo(iso: string): string {
  const delta = Date.now() - Date.parse(iso);
  const mins = Math.max(0, Math.round(delta / 60_000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

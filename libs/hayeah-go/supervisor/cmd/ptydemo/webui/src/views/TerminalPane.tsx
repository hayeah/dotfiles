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
  // No header: the sidebar card carries all session metadata and
  // the close control. Terminal pane is pure terminal, padded in
  // black so the ghostty-web canvas has a visible bezel. The outer
  // wrapper owns the padding + bg; the inner div is what ghostty-
  // web mounts into (canvas children fill 100% of their parent,
  // so padding has to live one level up).
  return (
    <div className="flex flex-1 flex-col bg-[#0f1018] p-3">
      <div className="relative flex min-h-0 flex-1 overflow-hidden rounded-sm bg-[#0f1018]">
        <TerminalHost
          key={session.key}
          onReady={(mount) => mountTerminal(mount, ds, session.key)}
        />
      </div>
    </div>
  );
});

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


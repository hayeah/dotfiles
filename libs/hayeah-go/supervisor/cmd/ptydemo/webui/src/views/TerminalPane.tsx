import { observer } from "mobx-react-lite";
import { useEffect, useRef } from "react";
import type { DataSource } from "../data/source";
import type { SessionSummary } from "../data/types";

interface Props {
  ds: DataSource;
  session: SessionSummary;
}

// TerminalPane renders a single session's PTY in the main column.
// No header: the sidebar card carries all session metadata and the
// close control. Pane is pure terminal, padded in black so the
// ghostty-web canvas has a visible bezel. The outer wrapper owns
// the padding + bg; the inner div is what ghostty-web mounts into
// (canvas children fill 100% of their parent, so padding has to
// live one level up).
export const TerminalPane = observer(function TerminalPane({ ds, session }: Props) {
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
// bidirectional AttachStream. FitAddon handles container-fit:
// fit() once on mount (sets initial cols/rows + triggers the
// backend resize via the onResize event wired to stream.resize),
// observeResize() keeps it sized as the window changes. Returns a
// disposer that the effect uses on unmount.
function mountTerminal(mount: HTMLDivElement, ds: DataSource, sessionKey: string) {
  let disposed = false;
  const teardown: Array<() => void> = [];

  (async () => {
    const { init, Terminal, FitAddon } = await import("ghostty-web");
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

    // Backend → terminal bytes.
    const unsubscribe = stream.onBytes((bytes) => {
      term.write(bytes);
    });
    teardown.push(unsubscribe);

    // Terminal → backend input (keystrokes, paste).
    const onDataDispose = term.onData?.((data: string) => {
      stream.send(new TextEncoder().encode(data));
    });
    if (onDataDispose) teardown.push(() => onDataDispose.dispose?.());

    // Fit-to-container. The addon sets term.cols/rows based on
    // mount's client dimensions; the onResize event fires
    // synchronously inside fit(), which is our one place to
    // forward the size to the remote PTY.
    const fit = new FitAddon();
    term.loadAddon(fit);

    const onResizeDispose = term.onResize?.(({ cols, rows }: { cols: number; rows: number }) => {
      stream.resize(cols, rows);
    });
    if (onResizeDispose) teardown.push(() => onResizeDispose.dispose?.());

    // Initial fit (plus whatever observeResize schedules after).
    // Wrap in rAF so the mount has been laid out.
    requestAnimationFrame(() => {
      if (disposed) return;
      try {
        fit.fit();
      } catch {
        // If fit fails (container not sized yet), observeResize
        // will catch it on the next frame.
      }
      fit.observeResize();
    });
    teardown.push(() => fit.dispose?.());
  })().catch((err) => {
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

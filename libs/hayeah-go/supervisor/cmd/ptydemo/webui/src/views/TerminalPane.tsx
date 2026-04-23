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
//
// The inner `<TerminalHost>` is keyed by `session.key`, so switching
// sessions unmounts + remounts it — guaranteeing a fresh Terminal,
// canvas, and WS attach per session. Any live render of the prior
// session is abandoned with its dying DOM node, never blending into
// the new session's canvas.
export const TerminalPane = observer(function TerminalPane({ ds, session }: Props) {
  return (
    <div className="flex flex-1 flex-col bg-[#0f1018] p-3">
      <div className="relative flex min-h-0 flex-1 overflow-hidden rounded-sm bg-[#0f1018]">
        <TerminalHost key={session.key} ds={ds} sessionKey={session.key} />
      </div>
    </div>
  );
});

// TerminalHost owns exactly one Terminal lifecycle. The effect runs
// once on mount (deps are the stable identity values sessionKey+ds),
// so parent re-renders from the 1s polling observer don't retear the
// Terminal down. A new session shows up as a key change on the
// parent, which unmounts this component entirely and remounts a
// fresh one.
function TerminalHost({ ds, sessionKey }: { ds: DataSource; sessionKey: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    return mountTerminal(ref.current, ds, sessionKey);
  }, [ds, sessionKey]);
  return <div ref={ref} className="h-full w-full min-h-0" />;
}

// mountTerminal lazily imports ghostty-web, initializes the WASM
// runtime once, constructs a Terminal, and wires up the
// bidirectional AttachStream. FitAddon handles container-fit:
// fit() once on mount (sets initial cols/rows + triggers the
// backend resize via the onResize event wired to stream.resize),
// observeResize() keeps it sized as the window changes. Returns a
// disposer that the effect uses on unmount.
//
// Ordering is load-bearing: we fit + clear BEFORE attaching the
// stream, and we mask the canvas immediately after `term.open`.
// Two reasons:
//
//   - Ghostty-web 0.3.0 fires a synchronous first render from
//     inside `term.open()` — before our code gets a chance to run.
//     After many session switches the wasmTerm's freshly-allocated
//     grid sometimes starts with non-zero cells (content bleeding
//     from a prior-disposed emulator in the same shared WASM
//     memory), and those stale cells paint onto the fresh canvas
//     during that first sync render. Overlaying the canvas with a
//     solid fill of the theme background right after open clobbers
//     those pixels before the user can see them.
//   - `term.reset()` frees and recreates the wasmTerm, so the next
//     render frame walks an emulator we *know* is empty. After
//     reset + fit, whatever bytes the server sends on the new
//     attach land on a known-clean grid at the correct final size;
//     the snapshot's cursor-positioned writes don't need to touch
//     every cell because every cell was already cleared.
//
// If either step is skipped, stale content from a prior session
// can survive onto the new session's canvas.
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

    // Mask pixels laid down by the synchronous first render in
    // `term.open()` (see the block comment above mountTerminal).
    const canvas = mount.querySelector("canvas");
    if (canvas instanceof HTMLCanvasElement) {
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#0f1018";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }
    }

    // Fit BEFORE reset so reset's fresh wasmTerm is allocated at
    // the final cols/rows — avoids later `wasmTerm.resize` from
    // 80×24 to (say) 200×44 leaving the extended cells in whatever
    // state the shared-WASM allocator happened to return.
    const fit = new FitAddon();
    term.loadAddon(fit);
    teardown.push(() => fit.dispose?.());
    try {
      fit.fit();
    } catch {
      // If fit fails (container not sized yet), observeResize
      // will catch it on the next frame.
    }
    fit.observeResize();

    // Now recreate the wasmTerm at the final dimensions so every
    // subsequent render frame walks a grid we know to be empty.
    term.reset?.();

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

    // Ongoing container-fit events — each fit() fires onResize,
    // which we forward to the remote PTY.
    const onResizeDispose = term.onResize?.(({ cols, rows }: { cols: number; rows: number }) => {
      stream.resize(cols, rows);
    });
    if (onResizeDispose) teardown.push(() => onResizeDispose.dispose?.());

    // Send the initial (post-fit) size to the backend so the
    // snapshot-then-live stream is shaped correctly.
    stream.resize(term.cols, term.rows);
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

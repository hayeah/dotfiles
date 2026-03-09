import { useState, useEffect, useMemo } from "react"

interface Service {
  hash: string
  hashid: string
  key?: string
  status: string
  port?: number
  no_port?: boolean
  tailnet: boolean
  url?: string
  cwd: string
  cmd: string[]
  last_up: string
  error?: string
}

function StatusBadge({ status, error }: { status: string; error?: string }) {
  const colors: Record<string, string> = {
    running: "bg-success/20 text-success",
    stopped: "bg-muted text-muted-foreground",
    unknown: "bg-warning/20 text-warning",
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? colors.unknown}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${status === "running" ? "bg-success" : status === "stopped" ? "bg-muted-foreground" : "bg-warning"}`} />
      {status}
      {error && <span className="text-destructive ml-1" title={error}>!</span>}
    </span>
  )
}

function ServiceCard({ svc }: { svc: Service }) {
  const name = svc.key || svc.hashid
  const cmdStr = svc.cmd.join(" ")
  const ago = timeAgo(svc.last_up)

  return (
    <div className="rounded-lg border border-border bg-background p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm truncate">{name}</h3>
          <span className="text-xs text-muted-foreground font-mono">{svc.hashid}</span>
        </div>
        <StatusBadge status={svc.status} error={svc.error} />
      </div>

      <div className="space-y-2 text-xs">
        {svc.port && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-12 shrink-0">port</span>
            <span className="font-mono font-medium">{svc.port}</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground w-12 shrink-0">cwd</span>
          <span className="font-mono truncate" title={svc.cwd}>{shortenPath(svc.cwd)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground w-12 shrink-0">cmd</span>
          <span className="font-mono truncate" title={cmdStr}>{cmdStr}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground w-12 shrink-0">last up</span>
          <span title={svc.last_up}>{ago}</span>
        </div>
        {svc.url && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-12 shrink-0">url</span>
            <a href={svc.url} className="text-primary underline truncate" target="_blank" rel="noreferrer">{svc.url}</a>
          </div>
        )}
        {svc.tailnet && (
          <span className="inline-block rounded bg-accent px-1.5 py-0.5 text-accent-foreground text-[10px] font-medium">tailnet</span>
        )}
      </div>
    </div>
  )
}

function shortenPath(p: string): string {
  return p.replace(/^\/Users\/[^/]+/, "~")
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

type StatusFilter = "all" | "running" | "stopped"

export function App() {
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")

  useEffect(() => {
    fetch("/api/services")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setServices)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    return services.filter((svc) => {
      if (statusFilter !== "all" && svc.status !== statusFilter) return false
      if (search) {
        const q = search.toLowerCase()
        const haystack = [svc.key, svc.hashid, svc.cwd, ...svc.cmd].join(" ").toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [services, search, statusFilter])

  const counts = useMemo(() => {
    const c = { all: services.length, running: 0, stopped: 0 }
    for (const s of services) {
      if (s.status === "running") c.running++
      else if (s.status === "stopped") c.stopped++
    }
    return c
  }, [services])

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold">devport</h1>
        <p className="text-sm text-muted-foreground">Service dashboard</p>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-6 space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="Filter services..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <div className="flex gap-1">
            {(["all", "running", "stopped"] as StatusFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === f
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {f} ({counts[f]})
              </button>
            ))}
          </div>
        </div>

        {loading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {error && <p className="text-sm text-destructive">Error: {error}</p>}

        {!loading && !error && filtered.length === 0 && (
          <p className="text-sm text-muted-foreground">No services match your filter.</p>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((svc) => (
            <ServiceCard key={svc.hash} svc={svc} />
          ))}
        </div>
      </main>
    </div>
  )
}

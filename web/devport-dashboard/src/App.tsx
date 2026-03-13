import { useState, useEffect, useMemo } from "react"

interface Service {
  key: string
  status: string
  health: string
  pid: number
  supervisor_pid: number
  port: number
  no_port: boolean
  restart_count: number
  public_hostname?: string
  issues?: string[]
  drift?: string[]
  last_error?: string
  last_exit_code?: number
  last_reason?: string
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-success/20 text-success",
    stopped: "bg-muted text-muted-foreground",
    starting: "bg-warning/20 text-warning",
    failed: "bg-destructive/20 text-destructive",
  }
  const dotColors: Record<string, string> = {
    running: "bg-success",
    stopped: "bg-muted-foreground",
    starting: "bg-warning",
    failed: "bg-destructive",
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? colors.stopped}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dotColors[status] ?? dotColors.stopped}`} />
      {status}
    </span>
  )
}

function HealthBadge({ health }: { health: string }) {
  if (health === "healthy") return null
  const color = health === "unhealthy" ? "text-destructive" : "text-muted-foreground"
  return <span className={`text-xs ${color}`}>{health}</span>
}

function ServiceCard({ svc }: { svc: Service }) {
  const url = svc.public_hostname ? `https://${svc.public_hostname}` : undefined
  const issues = svc.issues ?? svc.drift ?? []

  return (
    <div className="rounded-lg border border-border bg-background p-3 shadow-sm transition-shadow sm:p-4 sm:hover:shadow-md">
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm truncate">{svc.key}</h3>
          <HealthBadge health={svc.health} />
        </div>
        <div className="shrink-0 self-start">
          <StatusBadge status={svc.status} />
        </div>
      </div>

      <div className="space-y-2 text-xs">
        {!svc.no_port && svc.port > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-12 shrink-0">port</span>
            <span className="font-mono font-medium">{svc.port}</span>
          </div>
        )}
        {svc.pid > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-12 shrink-0">pid</span>
            <span className="font-mono">{svc.pid}</span>
          </div>
        )}
        {svc.restart_count > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-12 shrink-0">restarts</span>
            <span className="font-mono">{svc.restart_count}</span>
          </div>
        )}
        {url && (
          <div className="flex items-start gap-2">
            <span className="text-muted-foreground w-12 shrink-0">url</span>
            <a href={url} className="min-w-0 break-all text-primary underline" target="_blank" rel="noreferrer">{svc.public_hostname}</a>
          </div>
        )}
        {issues.length > 0 && (
          <div className="flex items-start gap-2">
            <span className="text-warning w-12 shrink-0">issues</span>
            <ul className="text-warning">
              {issues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          </div>
        )}
        {svc.last_error && (
          <div className="flex items-start gap-2">
            <span className="text-destructive w-12 shrink-0">error</span>
            <span className="text-destructive truncate" title={svc.last_error}>{svc.last_error}</span>
          </div>
        )}
      </div>
    </div>
  )
}

type StatusFilter = "all" | "running" | "stopped" | "failed"

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
        if (!svc.key.toLowerCase().includes(q)) return false
      }
      return true
    })
  }, [services, search, statusFilter])

  const counts = useMemo(() => {
    const c = { all: services.length, running: 0, stopped: 0, failed: 0 }
    for (const s of services) {
      if (s.status === "running") c.running++
      else if (s.status === "stopped") c.stopped++
      else if (s.status === "failed") c.failed++
    }
    return c
  }, [services])

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border px-4 py-4 sm:px-6">
        <h1 className="text-lg font-semibold">devport</h1>
        <p className="text-sm text-muted-foreground">Service dashboard</p>
      </header>

      <main className="mx-auto max-w-5xl space-y-4 px-4 py-6 sm:px-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="Filter services..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <div className="flex flex-wrap gap-1">
            {(["all", "running", "stopped", "failed"] as StatusFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className={`min-h-9 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
            <ServiceCard key={svc.key} svc={svc} />
          ))}
        </div>
      </main>
    </div>
  )
}

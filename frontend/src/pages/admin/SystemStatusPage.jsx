import { useEffect, useState } from 'react'
import { getHealth, getReady } from '@/api/system'
import { Spinner } from '@/components/ui'

function statusClass(value) {
  if (String(value).startsWith('ok')) return 'bg-emerald-100 text-emerald-700'
  if (String(value).startsWith('warn')) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-700'
}

function displayServiceName(value) {
  if (!value || value === 'CustomerHub API') return 'WorkDesk API'
  return value
}

export default function SystemStatusPage() {
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState(null)
  const [ready, setReady] = useState(null)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    const [healthResult, readyResult] = await Promise.allSettled([getHealth(), getReady()])
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
    else setError(healthResult.reason?.message ?? 'Health check failed')
    if (readyResult.status === 'fulfilled') setReady(readyResult.value)
    else setReady(readyResult.reason?.response?.data ?? { status: 'degraded', checks: { ready: readyResult.reason?.message ?? 'Ready check failed' } })
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">System Status</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Backend liveness and dependency readiness.</p>
        </div>
        <button onClick={load} className="px-3 py-2 rounded-lg border border-input text-sm font-medium hover:bg-muted">Refresh</button>
      </div>

      {error && <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center py-20"><Spinner className="w-5 h-5" /></div>
      ) : (
        <div className="grid gap-4">
          <section className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-foreground">Health</p>
                <p className="text-sm text-muted-foreground">{displayServiceName(health?.service)} · {health?.version ?? '—'}</p>
              </div>
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusClass(health?.status ?? 'error')}`}>
                {health?.status ?? 'error'}
              </span>
            </div>
          </section>

          <section className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="font-semibold text-foreground">Readiness</p>
                <p className="text-sm text-muted-foreground">Database, Redis, email outbox and SMTP configuration.</p>
              </div>
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusClass(ready?.status ?? 'error')}`}>
                {ready?.status ?? 'error'}
              </span>
            </div>
            <div className="grid gap-2">
              {Object.entries(ready?.checks ?? {}).map(([name, value]) => (
                <div key={name} className="flex items-start justify-between gap-4 rounded-lg bg-muted/30 px-3 py-2">
                  <span className="text-sm font-medium text-foreground">{name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium text-right ${statusClass(value)}`}>
                    {String(value)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

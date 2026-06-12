import { useState, useEffect, useCallback } from 'react'
import { subDays } from 'date-fns'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Spinner } from '@/components/ui'
import { useRole } from '@/hooks/useRole'
import { getTicketAnalytics, getSLAAnalytics, getAgentAnalytics, getRevenueAnalytics } from '@/api/analytics'
import { listOrganizations } from '@/api/organizations'
import { formatCurrencyVND, formatDate } from '@/lib/utils'

// ── helpers ────────────────────────────────────────────────────────────────────

function fmtVND(value) {
  if (value == null) return '—'
  return formatCurrencyVND(value)
}

function fmtDate(str) {
  return formatDate(str)
}

function todayISO() { return new Date().toISOString().slice(0, 10) }
function daysAgoISO(n) { return subDays(new Date(), n).toISOString().slice(0, 10) }

// Pie chart colours
const PIE_COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6']

// ── sub-components ─────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color = 'text-foreground' }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 flex flex-col gap-1">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value ?? '—'}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  )
}

function SectionHeader({ title }) {
  return (
    <h2 className="text-base font-semibold text-foreground mb-4">{title}</h2>
  )
}

function LoadingSkeleton({ rows = 4 }) {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-8 bg-muted rounded-lg" />
      ))}
    </div>
  )
}

function ErrorBlock({ message }) {
  return (
    <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
      {message}
    </div>
  )
}

// ── SLA compliance colour ──────────────────────────────────────────────────────

function slaColor(rate) {
  if (rate >= 80) return 'text-emerald-600'
  if (rate >= 60) return 'text-yellow-500'
  return 'text-red-600'
}

// ── Sortable agent table ───────────────────────────────────────────────────────

const AGENT_COLS = [
  { key: 'name',                  label: 'Agent' },
  { key: 'tickets_assigned',      label: 'Assigned' },
  { key: 'tickets_resolved',      label: 'Resolved' },
  { key: 'avg_resolution_hours',  label: 'Avg Res. (h)' },
  { key: 'sla_compliance_rate',   label: 'SLA Rate' },
]

function AgentTable({ agents }) {
  const [sortKey, setSortKey] = useState('tickets_assigned')
  const [sortAsc, setSortAsc] = useState(false)

  const sorted = [...agents].sort((a, b) => {
    const av = a[sortKey] ?? 0
    const bv = b[sortKey] ?? 0
    if (typeof av === 'string') return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av)
    return sortAsc ? av - bv : bv - av
  })

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc((v) => !v)
    else { setSortKey(key); setSortAsc(false) }
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            {AGENT_COLS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="px-4 py-3 text-left font-semibold text-muted-foreground cursor-pointer hover:text-foreground select-none whitespace-nowrap"
              >
                {col.label}
                {sortKey === col.key && (
                  <span className="ml-1">{sortAsc ? '↑' : '↓'}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sorted.map((a) => (
            <tr key={a.user_id} className="hover:bg-muted/30 transition-colors">
              <td className="px-4 py-3 font-medium text-foreground">{a.name}</td>
              <td className="px-4 py-3 text-muted-foreground">{a.tickets_assigned ?? 0}</td>
              <td className="px-4 py-3 text-muted-foreground">{a.tickets_resolved ?? 0}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {a.avg_resolution_hours != null ? a.avg_resolution_hours.toFixed(1) : '—'}
              </td>
              <td className={`px-4 py-3 font-semibold ${slaColor(a.sla_compliance_rate ?? 0)}`}>
                {a.sla_compliance_rate != null ? `${a.sla_compliance_rate.toFixed(1)}%` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function AnalyticsDashboard() {
  const { isAdmin } = useRole()

  // Date range — default last 30 days
  const [fromDate, setFromDate] = useState(daysAgoISO(29))
  const [toDate, setToDate] = useState(todayISO())
  const [orgId, setOrgId] = useState('')

  // Orgs for filter dropdown
  const [orgs, setOrgs] = useState([])

  // Analytics data
  const [ticketData, setTicketData] = useState(null)
  const [slaData, setSlaData] = useState(null)
  const [agentData, setAgentData] = useState(null)
  const [revenueData, setRevenueData] = useState(null)

  // Loading/error states
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [loadingSla, setLoadingSla] = useState(false)
  const [loadingAgents, setLoadingAgents] = useState(false)
  const [loadingRevenue, setLoadingRevenue] = useState(false)

  const [errorTickets, setErrorTickets] = useState('')
  const [errorSla, setErrorSla] = useState('')
  const [errorAgents, setErrorAgents] = useState('')
  const [errorRevenue, setErrorRevenue] = useState('')

  // Org fetch error state
  const [orgError, setOrgError] = useState(false)

  // Load orgs on mount (admin only)
  useEffect(() => {
    if (!isAdmin) return
    listOrganizations({ per_page: 200 })
      .then((data) => {
        const items = Array.isArray(data) ? data : (data?.items ?? [])
        setOrgs(items)
      })
      .catch(() => setOrgError(true))
  }, [isAdmin])

  const fetchAll = useCallback((signal) => {
    const params = {
      from_date: fromDate,
      to_date: toDate,
      ...(orgId ? { org_id: orgId } : {}),
    }

    // Ticket analytics
    setLoadingTickets(true)
    setErrorTickets('')
    getTicketAnalytics(params, signal)
      .then((r) => setTicketData(r.data))
      .catch((e) => {
        if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorTickets(e.message || 'Failed to load ticket analytics')
      })
      .finally(() => setLoadingTickets(false))

    // SLA analytics
    setLoadingSla(true)
    setErrorSla('')
    getSLAAnalytics(params, signal)
      .then((r) => setSlaData(r.data))
      .catch((e) => {
        if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorSla(e.message || 'Failed to load SLA analytics')
      })
      .finally(() => setLoadingSla(false))

    if (isAdmin) {
      // Agent analytics
      setLoadingAgents(true)
      setErrorAgents('')
      getAgentAnalytics(params, signal)
        .then((r) => setAgentData(r.data))
        .catch((e) => {
          if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorAgents(e.message || 'Failed to load agent analytics')
        })
        .finally(() => setLoadingAgents(false))

      // Revenue analytics
      setLoadingRevenue(true)
      setErrorRevenue('')
      getRevenueAnalytics(params, signal)
        .then((r) => setRevenueData(r.data))
        .catch((e) => {
          if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorRevenue(e.message || 'Failed to load revenue analytics')
        })
        .finally(() => setLoadingRevenue(false))
    }
  }, [fromDate, toDate, orgId, isAdmin])

  // Fetch on mount and when filters change; abort stale requests
  useEffect(() => {
    const controller = new AbortController()
    fetchAll(controller.signal)
    return () => controller.abort()
  }, [fetchAll])

  // ── Derived data ──────────────────────────────────────────────────────────────

  const byStatus = ticketData?.by_status ?? {}
  const byPriority = ticketData?.by_priority ?? {}
  const dailyTrend = ticketData?.daily_trend ?? []

  // Pie chart data from by_priority
  const priorityPieData = Object.entries(byPriority).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: value ?? 0,
  }))

  // Daily trend — format dates for display
  const trendData = dailyTrend.map((d) => ({
    ...d,
    label: fmtDate(d.date),
  }))

  // SLA by_priority rows
  const slaByPriority = Object.entries(slaData?.by_priority ?? {}).map(([priority, stats]) => ({
    priority: priority.charAt(0).toUpperCase() + priority.slice(1),
    met: stats.met ?? 0,
    breached: stats.breached ?? 0,
    rate: stats.rate ?? 0,
  }))

  // Revenue monthly
  const revenueByMonth = (revenueData?.by_month ?? []).map((m) => ({
    ...m,
    label: m.month ? m.month.slice(0, 7) : '',
  }))

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="p-6 space-y-8 max-w-screen-xl mx-auto">
      {/* ── Page header ── */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Analytics Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">View ticket, SLA, and performance metrics.</p>
      </div>

      {/* ── Filters ── */}
      <div className="bg-card border border-border rounded-xl p-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">From</label>
            <input
              type="date"
              value={fromDate}
              max={toDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">To</label>
            <input
              type="date"
              value={toDate}
              min={fromDate}
              onChange={(e) => setToDate(e.target.value)}
              className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          {isAdmin && orgs.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Organization</label>
              <select
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">All organizations</option>
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>{o.name}</option>
                ))}
              </select>
              {orgError && <p className="text-xs text-red-500 mt-1">Failed to load organizations</p>}
            </div>
          )}
          <button
            onClick={() => {
              const controller = new AbortController()
              fetchAll(controller.signal)
            }}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold hover:brightness-110 transition-all"
          >
            Apply
          </button>
        </div>
        {!isAdmin && (
          <p className="text-sm text-muted-foreground mt-2">
            Showing data for your assigned organizations only.
          </p>
        )}
      </div>

      {/* ── Section 1: Ticket Overview ── */}
      <section>
        <SectionHeader title="Ticket Overview" />

        {loadingTickets ? (
          <LoadingSkeleton rows={3} />
        ) : errorTickets ? (
          <ErrorBlock message={errorTickets} />
        ) : (
          <>
            {/* Stat cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
              <StatCard label="Total" value={ticketData?.total ?? 0} />
              <StatCard label="Open" value={byStatus.open ?? 0} color="text-blue-600" />
              <StatCard label="In Progress" value={byStatus.in_progress ?? 0} color="text-yellow-600" />
              <StatCard label="Resolved" value={byStatus.resolved ?? 0} color="text-emerald-600" />
              <StatCard
                label="Avg Resolution"
                value={ticketData?.avg_resolution_hours != null
                  ? `${ticketData.avg_resolution_hours.toFixed(1)}h`
                  : '—'}
                sub="hours"
              />
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Bar chart: daily trend */}
              <div className="lg:col-span-2 bg-card border border-border rounded-xl p-5">
                <p className="text-sm font-semibold text-foreground mb-4">Daily Ticket Trend</p>
                {trendData.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-10">No data for this period</p>
                ) : (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={trendData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 10 }}
                        interval="preserveStartEnd"
                        stroke="hsl(var(--muted-foreground))"
                      />
                      <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                      <Tooltip
                        contentStyle={{
                          background: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="count" fill="#6366f1" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Pie chart: by priority */}
              <div className="bg-card border border-border rounded-xl p-5">
                <p className="text-sm font-semibold text-foreground mb-4">Tickets by Priority</p>
                {priorityPieData.every((d) => d.value === 0) ? (
                  <p className="text-sm text-muted-foreground text-center py-10">No data</p>
                ) : (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={priorityPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={90}
                        paddingAngle={2}
                        dataKey="value"
                        label={({ name, percent }) =>
                          percent > 0.05 ? `${name} ${(percent * 100).toFixed(0)}%` : ''
                        }
                        labelLine={false}
                      >
                        {priorityPieData.map((_, i) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </>
        )}
      </section>

      {/* ── Section 2: SLA Compliance ── */}
      <section>
        <SectionHeader title="SLA Compliance" />

        {loadingSla ? (
          <LoadingSkeleton rows={3} />
        ) : errorSla ? (
          <ErrorBlock message={errorSla} />
        ) : (
          <>
            {/* Big compliance number */}
            <div className="flex flex-wrap gap-6 items-center mb-6">
              <div className="bg-card border border-border rounded-xl p-6 text-center min-w-[160px]">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                  Overall Compliance
                </p>
                <p className={`text-4xl font-bold ${slaColor(slaData?.compliance_rate ?? 0)}`}>
                  {slaData?.compliance_rate != null
                    ? `${slaData.compliance_rate.toFixed(1)}%`
                    : '—'}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {slaData?.sla_met ?? 0} met / {slaData?.sla_breached ?? 0} breached
                </p>
              </div>
            </div>

            {/* SLA by priority table */}
            {slaByPriority.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Priority</th>
                      <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Met</th>
                      <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Breached</th>
                      <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {slaByPriority.map((row) => (
                      <tr key={row.priority} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3 font-medium text-foreground">{row.priority}</td>
                        <td className="px-4 py-3 text-emerald-600 font-medium">{row.met}</td>
                        <td className="px-4 py-3 text-red-500 font-medium">{row.breached}</td>
                        <td className={`px-4 py-3 font-semibold ${slaColor(row.rate)}`}>
                          {row.rate.toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Section 3: Agent Performance (admin only) ── */}
      {isAdmin && (
        <section>
          <SectionHeader title="Agent Performance" />

          {loadingAgents ? (
            <LoadingSkeleton rows={4} />
          ) : errorAgents ? (
            <ErrorBlock message={errorAgents} />
          ) : !agentData?.agents?.length ? (
            <p className="text-sm text-muted-foreground">No agent data available.</p>
          ) : (
            <AgentTable agents={agentData.agents} />
          )}
        </section>
      )}

      {/* ── Section 4: Revenue (admin only) ── */}
      {isAdmin && (
        <section>
          <SectionHeader title="Revenue" />

          {loadingRevenue ? (
            <LoadingSkeleton rows={3} />
          ) : errorRevenue ? (
            <ErrorBlock message={errorRevenue} />
          ) : (
            <>
              {/* Stat cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                <StatCard
                  label="Total Invoiced"
                  value={fmtVND(revenueData?.total_invoiced)}
                  color="text-blue-600"
                />
                <StatCard
                  label="Total Paid"
                  value={fmtVND(revenueData?.total_paid)}
                  color="text-emerald-600"
                />
                <StatCard
                  label="Overdue"
                  value={fmtVND(revenueData?.total_overdue)}
                  color="text-red-600"
                />
              </div>

              {/* Monthly revenue bar chart */}
              {revenueByMonth.length > 0 && (
                <div className="bg-card border border-border rounded-xl p-5 mb-6">
                  <p className="text-sm font-semibold text-foreground mb-4">Monthly Revenue</p>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={revenueByMonth} margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 10 }}
                        stroke="hsl(var(--muted-foreground))"
                      />
                      <YAxis
                        tick={{ fontSize: 10 }}
                        stroke="hsl(var(--muted-foreground))"
                        tickFormatter={(v) => new Intl.NumberFormat('vi-VN', { notation: 'compact' }).format(v)}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                        formatter={(value, name) => [fmtVND(value), name]}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Bar dataKey="invoiced" name="Invoiced" fill="#6366f1" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="paid" name="Paid" fill="#22c55e" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Revenue by org table */}
              {(revenueData?.by_org ?? []).length > 0 && (
                <div className="overflow-x-auto rounded-xl border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Organization</th>
                        <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {revenueData.by_org.map((row) => (
                        <tr key={row.org_id} className="hover:bg-muted/30 transition-colors">
                          <td className="px-4 py-3 font-medium text-foreground">{row.org_name}</td>
                          <td className="px-4 py-3 text-foreground">{fmtVND(row.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
      )}
    </div>
  )
}

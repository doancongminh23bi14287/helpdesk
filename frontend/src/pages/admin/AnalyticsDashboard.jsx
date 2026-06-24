import { useState, useEffect, useCallback } from 'react'
import { subDays } from 'date-fns'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Spinner } from '@/components/ui'
import { useRole } from '@/hooks/useRole'
import AiStatusBadge from '@/components/ai/AiStatusBadge'
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

// Chart colour palette
const STATUS_COLORS = {
  Open:        '#2563EB',
  'In Progress': '#0EA5E9',
  Waiting:     '#F59E0B',
  Resolved:    '#10B981',
  Closed:      '#6B7280',
}

const PRIORITY_COLORS = {
  Low:    '#10B981',
  Medium: '#0EA5E9',
  High:   '#2563EB',
  Urgent: '#6366F1',
}

const SLA_STATE_COLORS = {
  green:    '#10B981',
  amber:    '#F59E0B',
  red:      '#EF4444',
  breached: '#7C3AED',
}

const CHART_COLORS = ['#2563EB', '#0EA5E9', '#10B981', '#14B8A6', '#6366F1', '#F59E0B']

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
  return <h2 className="text-base font-semibold text-foreground mb-4">{title}</h2>
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

function EmptyState({ message = 'No data for this period' }) {
  return (
    <p className="text-sm text-muted-foreground text-center py-10">{message}</p>
  )
}

const tooltipStyle = {
  background: 'hsl(var(--card))',
  border: '1px solid hsl(var(--border))',
  borderRadius: '8px',
  fontSize: '12px',
}

// ── SLA colour helper ──────────────────────────────────────────────────────────

function slaColor(rate) {
  if (rate >= 80) return 'text-emerald-600'
  if (rate >= 60) return 'text-yellow-500'
  return 'text-red-600'
}

// ── Sortable agent table ───────────────────────────────────────────────────────

const AGENT_COLS = [
  { key: 'name',                 label: 'Agent' },
  { key: 'tickets_open',         label: 'Open' },
  { key: 'tickets_assigned',     label: 'Assigned' },
  { key: 'tickets_resolved',     label: 'Resolved' },
  { key: 'avg_resolution_hours', label: 'Avg Res. (h)' },
  { key: 'sla_compliance_rate',  label: 'SLA Rate' },
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
                {sortKey === col.key && <span className="ml-1">{sortAsc ? '↑' : '↓'}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sorted.map((a) => (
            <tr key={a.user_id} className="hover:bg-muted/30 transition-colors">
              <td className="px-4 py-3 font-medium text-foreground whitespace-nowrap">{a.name}</td>
              <td className="px-4 py-3 text-blue-600 font-medium">{a.tickets_open ?? 0}</td>
              <td className="px-4 py-3 text-muted-foreground">{a.tickets_assigned ?? 0}</td>
              <td className="px-4 py-3 text-emerald-600 font-medium">{a.tickets_resolved ?? 0}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {a.avg_resolution_hours != null ? `${a.avg_resolution_hours.toFixed(1)}h` : '—'}
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

  const [fromDate, setFromDate] = useState(daysAgoISO(29))
  const [toDate, setToDate]     = useState(todayISO())
  const [orgId, setOrgId]       = useState('')

  const [orgs, setOrgs]         = useState([])

  const [ticketData,  setTicketData]  = useState(null)
  const [slaData,     setSlaData]     = useState(null)
  const [agentData,   setAgentData]   = useState(null)
  const [revenueData, setRevenueData] = useState(null)

  const [loadingTickets, setLoadingTickets]   = useState(false)
  const [loadingSla,     setLoadingSla]       = useState(false)
  const [loadingAgents,  setLoadingAgents]    = useState(false)
  const [loadingRevenue, setLoadingRevenue]   = useState(false)

  const [errorTickets, setErrorTickets] = useState('')
  const [errorSla,     setErrorSla]     = useState('')
  const [errorAgents,  setErrorAgents]  = useState('')
  const [errorRevenue, setErrorRevenue] = useState('')

  const [revenueYear, setRevenueYear] = useState(new Date().getFullYear())
  const [orgError,    setOrgError]    = useState(false)

  useEffect(() => {
    if (!isAdmin) return
    listOrganizations({ per_page: 200 })
      .then((data) => setOrgs(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setOrgError(true))
  }, [isAdmin])

  const fetchAll = useCallback((signal) => {
    const params = {
      from_date: fromDate,
      to_date:   toDate,
      ...(orgId ? { org_id: orgId } : {}),
    }

    setLoadingTickets(true); setErrorTickets('')
    getTicketAnalytics(params, signal)
      .then((r) => setTicketData(r.data))
      .catch((e) => { if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorTickets(e.message || 'Failed to load ticket analytics') })
      .finally(() => setLoadingTickets(false))

    setLoadingSla(true); setErrorSla('')
    getSLAAnalytics(params, signal)
      .then((r) => setSlaData(r.data))
      .catch((e) => { if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorSla(e.message || 'Failed to load SLA analytics') })
      .finally(() => setLoadingSla(false))

    if (isAdmin) {
      setLoadingAgents(true); setErrorAgents('')
      getAgentAnalytics(params, signal)
        .then((r) => setAgentData(r.data))
        .catch((e) => { if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorAgents(e.message || 'Failed to load agent analytics') })
        .finally(() => setLoadingAgents(false))

      setLoadingRevenue(true); setErrorRevenue('')
      getRevenueAnalytics({ year: revenueYear, ...(orgId ? { org_id: orgId } : {}) }, signal)
        .then((r) => setRevenueData(r.data))
        .catch((e) => { if (e.code !== 'ERR_CANCELED' && !e.__CANCEL__) setErrorRevenue(e.message || 'Failed to load revenue analytics') })
        .finally(() => setLoadingRevenue(false))
    }
  }, [fromDate, toDate, orgId, isAdmin, revenueYear])

  useEffect(() => {
    const controller = new AbortController()
    fetchAll(controller.signal)
    return () => controller.abort()
  }, [fetchAll])

  // ── Derived data ──────────────────────────────────────────────────────────────

  // by_status keys are exact enum values: "Open", "In Progress", "Waiting", "Resolved", "Closed"
  const byStatus   = ticketData?.by_status   ?? {}
  const byPriority = ticketData?.by_priority ?? {}
  const dailyTrend = ticketData?.daily_trend ?? []

  const statusBarData = Object.entries(byStatus).map(([name, value]) => ({ name, value }))

  const priorityPieData = Object.entries(byPriority).map(([name, value]) => ({ name, value }))

  const trendData = dailyTrend.map((d) => ({ ...d, label: fmtDate(d.date) }))

  // SLA state distribution
  const byStateRaw = slaData?.by_sla_state ?? {}
  const slaStateData = ['green', 'amber', 'red', 'breached']
    .filter((s) => byStateRaw[s] != null)
    .map((s) => ({ name: s.charAt(0).toUpperCase() + s.slice(1), value: byStateRaw[s], state: s }))

  const slaByPriority = Object.entries(slaData?.by_priority ?? {}).map(([priority, stats]) => ({
    priority: priority.charAt(0).toUpperCase() + priority.slice(1),
    met:      stats.met ?? 0,
    breached: stats.breached ?? 0,
    rate:     stats.rate ?? 0,
  }))

  const revenueByMonth = (revenueData?.by_month ?? []).map((m) => ({
    ...m,
    label: m.month ? m.month.slice(0, 7) : '',
  }))

  // Top KPI derived values
  const activeAgents = agentData?.agents?.length ?? 0
  const slaCompliance = slaData?.sla_state_compliance_rate ?? slaData?.compliance_rate ?? 0
  const slaBreached   = slaData?.sla_state_breached ?? slaData?.sla_breached ?? 0

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="p-6 space-y-8 max-w-screen-xl mx-auto">
      {/* ── Page header ── */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-foreground">Analytics Dashboard</h1>
          <AiStatusBadge />
        </div>
        <p className="text-sm text-muted-foreground mt-1">Ticket metrics, SLA compliance, and agent performance.</p>
      </div>

      {/* ── Filters ── */}
      <div className="bg-card border border-border rounded-xl p-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">From</label>
            <input
              type="date" value={fromDate} max={toDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">To</label>
            <input
              type="date" value={toDate} min={fromDate}
              onChange={(e) => setToDate(e.target.value)}
              className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          {isAdmin && orgs.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Organization</label>
              <select
                value={orgId} onChange={(e) => setOrgId(e.target.value)}
                className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">All organizations</option>
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
              {orgError && <p className="text-xs text-red-500 mt-1">Failed to load organizations</p>}
            </div>
          )}
          <button
            onClick={() => { const c = new AbortController(); fetchAll(c.signal) }}
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

      {/* ── Top KPI row ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Total Tickets"
          value={ticketData?.total ?? 0}
        />
        <StatCard
          label="SLA Compliance"
          value={slaData ? `${slaCompliance.toFixed(1)}%` : '—'}
          color={slaColor(slaCompliance)}
          sub="non-breached / total"
        />
        <StatCard
          label="SLA Breached"
          value={slaData ? slaBreached : '—'}
          color={slaBreached > 0 ? 'text-red-600' : 'text-emerald-600'}
        />
        {isAdmin && (
          <StatCard
            label="Active Agents"
            value={agentData ? activeAgents : '—'}
            sub="with assigned tickets"
          />
        )}
      </div>

      {/* ── Section 1: Ticket Overview ── */}
      <section>
        <SectionHeader title="Ticket Overview" />

        {loadingTickets ? <LoadingSkeleton rows={3} /> : errorTickets ? <ErrorBlock message={errorTickets} /> : (
          <>
            {/* Status + Priority stat cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
              <StatCard label="Open"        value={byStatus["Open"]          ?? 0} color="text-blue-600" />
              <StatCard label="In Progress" value={byStatus["In Progress"]   ?? 0} color="text-sky-500" />
              <StatCard label="Waiting"     value={byStatus["Waiting"]       ?? 0} color="text-yellow-500" />
              <StatCard label="Resolved"    value={byStatus["Resolved"]      ?? 0} color="text-emerald-600" />
              <StatCard label="Closed"      value={byStatus["Closed"]        ?? 0} color="text-muted-foreground" />
              <StatCard
                label="Avg Resolution"
                value={ticketData?.avg_resolution_hours != null
                  ? `${ticketData.avg_resolution_hours.toFixed(1)}h` : '—'}
                sub="hours (resolved)"
              />
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Line chart: daily trend */}
              <div className="lg:col-span-2 bg-card border border-border rounded-xl p-5">
                <p className="text-sm font-semibold text-foreground mb-4">Daily Ticket Trend (30 days)</p>
                {trendData.length === 0 ? <EmptyState /> : (
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={trendData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" allowDecimals={false} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Line type="monotone" dataKey="count" stroke="#2563EB" strokeWidth={2} dot={false} name="Tickets" />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Bar chart: by status */}
              <div className="bg-card border border-border rounded-xl p-5">
                <p className="text-sm font-semibold text-foreground mb-4">Tickets by Status</p>
                {statusBarData.length === 0 ? <EmptyState /> : (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={statusBarData} layout="vertical" margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" allowDecimals={false} />
                      <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={80} stroke="hsl(var(--muted-foreground))" />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Bar dataKey="value" name="Count" radius={[0, 3, 3, 0]}>
                        {statusBarData.map((entry) => (
                          <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? '#6366F1'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* Priority pie chart */}
            <div className="mt-6 bg-card border border-border rounded-xl p-5">
              <p className="text-sm font-semibold text-foreground mb-4">Tickets by Priority</p>
              {priorityPieData.every((d) => d.value === 0) ? <EmptyState /> : (
                <div className="flex justify-center">
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={priorityPieData}
                        cx="50%" cy="50%"
                        innerRadius={55} outerRadius={80}
                        paddingAngle={2} dataKey="value"
                        label={({ name, percent }) => percent > 0.05 ? `${name} ${(percent * 100).toFixed(0)}%` : ''}
                        labelLine={false}
                      >
                        {priorityPieData.map((entry) => (
                          <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name] ?? '#6366F1'} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </>
        )}
      </section>

      {/* ── Section 2: SLA ── */}
      <section>
        <SectionHeader title="SLA Compliance" />

        {loadingSla ? <LoadingSkeleton rows={3} /> : errorSla ? <ErrorBlock message={errorSla} /> : (
          <>
            <div className="flex flex-wrap gap-4 items-start mb-6">
              {/* Overall compliance */}
              <div className="bg-card border border-border rounded-xl p-6 text-center min-w-[160px]">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                  Overall Compliance
                </p>
                <p className={`text-4xl font-bold ${slaColor(slaData?.sla_state_compliance_rate ?? 0)}`}>
                  {slaData?.sla_state_compliance_rate != null
                    ? `${slaData.sla_state_compliance_rate.toFixed(1)}%` : '—'}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {slaData?.sla_state_breached ?? 0} breached tickets
                </p>
              </div>

              {/* Deadline-based breakdown mini-cards */}
              <div className="flex flex-col gap-2 justify-center">
                <p className="text-xs text-muted-foreground font-medium">Deadline-based</p>
                <div className="flex gap-4">
                  <div className="text-center">
                    <p className="text-lg font-bold text-emerald-600">{slaData?.sla_met ?? 0}</p>
                    <p className="text-xs text-muted-foreground">Met</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-red-600">{slaData?.sla_breached ?? 0}</p>
                    <p className="text-xs text-muted-foreground">Breached</p>
                  </div>
                  <div className="text-center">
                    <p className={`text-lg font-bold ${slaColor(slaData?.compliance_rate ?? 0)}`}>
                      {slaData?.compliance_rate != null ? `${slaData.compliance_rate.toFixed(1)}%` : '—'}
                    </p>
                    <p className="text-xs text-muted-foreground">Rate</p>
                  </div>
                </div>
              </div>
            </div>

            {/* SLA state distribution bar chart */}
            {slaStateData.length > 0 && (
              <div className="bg-card border border-border rounded-xl p-5 mb-6">
                <p className="text-sm font-semibold text-foreground mb-4">SLA State Distribution</p>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={slaStateData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                    <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" allowDecimals={false} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="value" name="Tickets" radius={[3, 3, 0, 0]}>
                      {slaStateData.map((entry) => (
                        <Cell key={entry.state} fill={SLA_STATE_COLORS[entry.state] ?? '#6366F1'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

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
          {loadingAgents ? <LoadingSkeleton rows={4} /> : errorAgents ? <ErrorBlock message={errorAgents} /> : (
            !agentData?.agents?.length
              ? <p className="text-sm text-muted-foreground">No agent data for this period.</p>
              : <AgentTable agents={agentData.agents} />
          )}
        </section>
      )}

      {/* ── Section 4: Revenue (admin only) ── */}
      {isAdmin && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-foreground">
              Revenue — {revenueData?.year ?? revenueYear}
            </h2>
            <select
              value={revenueYear}
              onChange={(e) => setRevenueYear(Number(e.target.value))}
              className="px-3 py-1.5 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {[new Date().getFullYear(), new Date().getFullYear() - 1, new Date().getFullYear() - 2].map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {loadingRevenue ? <LoadingSkeleton rows={3} /> : errorRevenue ? <ErrorBlock message={errorRevenue} /> : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                <StatCard label="Total Paid"     value={fmtVND(revenueData?.total_paid)}     color="text-emerald-600" sub="actual revenue received" />
                <StatCard label="Total Invoiced" value={fmtVND(revenueData?.total_invoiced)} color="text-blue-600"    sub="all issued invoices" />
                <StatCard label="Overdue"        value={fmtVND(revenueData?.total_overdue)}  color="text-red-600"     sub="unpaid past due" />
              </div>

              {revenueByMonth.length > 0 && (
                <div className="bg-card border border-border rounded-xl p-5 mb-6">
                  <p className="text-sm font-semibold text-foreground mb-4">Monthly Revenue — {revenueData?.year ?? revenueYear}</p>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={revenueByMonth} margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="label" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))"
                        tickFormatter={(v) => new Intl.NumberFormat('vi-VN', { notation: 'compact' }).format(v)} />
                      <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => [fmtVND(value), name]} />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Bar dataKey="invoiced" name="Invoiced" fill="#2563EB" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="paid"     name="Paid"     fill="#10B981" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

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

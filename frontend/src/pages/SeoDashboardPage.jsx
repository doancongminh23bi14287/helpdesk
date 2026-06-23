import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area,
} from 'recharts'
import { ArrowUpIcon, ArrowDownIcon, MinusIcon, PrinterIcon, BeakerIcon, LinkIcon, CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { keywords, rankHistory, rankKeywords, gscSummary, ga4Summary } from '@/data/seoMockData'
import client from '@/api/client'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

// ── Prototype banner ──────────────────────────────────────────────────────────

function PrototypeBanner() {
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-amber-300 bg-amber-50 text-amber-800 dark:bg-amber-900/20 dark:border-amber-700 dark:text-amber-300">
      <BeakerIcon className="w-5 h-5 flex-shrink-0 text-amber-500" />
      <div className="min-w-0">
        <span className="font-semibold text-sm">Prototype — sample data only.</span>
        <span className="text-sm ml-1.5">
          All metrics on this page are mock data. No live Google Search Console or GA4 integration exists yet.
        </span>
      </div>
      <span className="ml-auto flex-shrink-0 px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-amber-200 text-amber-700 dark:bg-amber-800 dark:text-amber-200">
        Preview
      </span>
    </div>
  )
}

// ── Mini sparkline using Recharts AreaChart ───────────────────────────────────

function Sparkline({ data, color }) {
  const pts = data.map((v, i) => ({ i, v }))
  return (
    <ResponsiveContainer width="100%" height={48}>
      <AreaChart data={pts} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`spark-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5}
              fill={`url(#spark-${color.replace('#', '')})`} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

// ── KPI card ─────────────────────────────────────────────────────────────────

function KpiCard({ title, badge, metrics, sparkline, sparkColor }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {badge && (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground">
            {badge}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {metrics.map(({ label, value, sub }) => (
          <div key={label}>
            <p className="text-[11px] text-muted-foreground uppercase tracking-wide">{label}</p>
            <p className="text-lg font-bold text-foreground leading-tight">{value}</p>
            {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
          </div>
        ))}
      </div>
      <Sparkline data={sparkline} color={sparkColor} />
    </div>
  )
}

// ── Keyword change pill ───────────────────────────────────────────────────────

function ChangePill({ change }) {
  if (change > 0) return (
    <span className="inline-flex items-center gap-0.5 text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5 text-xs font-semibold dark:text-emerald-400 dark:bg-emerald-900/20 dark:border-emerald-800">
      <ArrowUpIcon className="w-3 h-3" /> {change}
    </span>
  )
  if (change < 0) return (
    <span className="inline-flex items-center gap-0.5 text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5 text-xs font-semibold dark:text-red-400 dark:bg-red-900/20 dark:border-red-800">
      <ArrowDownIcon className="w-3 h-3" /> {Math.abs(change)}
    </span>
  )
  return (
    <span className="inline-flex items-center gap-0.5 text-muted-foreground bg-muted rounded-full px-2 py-0.5 text-xs font-semibold">
      <MinusIcon className="w-3 h-3" /> 0
    </span>
  )
}

// ── Keywords table ────────────────────────────────────────────────────────────

function KeywordsTable() {
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <h2 className="text-sm font-semibold text-foreground">Tracked Keywords</h2>
        <p className="text-xs text-muted-foreground mt-0.5">Position as of today vs. 30 days ago</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Keyword</th>
              <th className="text-center px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Pos.</th>
              <th className="text-center px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Change</th>
              <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Volume</th>
              <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">URL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {keywords.map((row) => (
              <tr key={row.keyword} className="hover:bg-muted/20 transition-colors">
                <td className="px-5 py-3 font-medium text-foreground">{row.keyword}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold ${
                    row.position <= 3 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                    : row.position <= 10 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                    : 'bg-muted text-muted-foreground'
                  }`}>
                    {row.position}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <ChangePill change={row.change} />
                </td>
                <td className="px-4 py-3 text-right text-muted-foreground tabular-nums">{row.volume.toLocaleString()}</td>
                <td className="px-5 py-3 text-muted-foreground text-xs truncate max-w-[180px]">{row.url}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Rank history chart ────────────────────────────────────────────────────────

function RankChart() {
  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="mb-1">
        <h2 className="text-sm font-semibold text-foreground">Keyword Rankings Over Time</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Lower position = better rank. Y-axis is inverted so improvements go up.
        </p>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={rankHistory} margin={{ top: 16, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: 'var(--color-muted-foreground, #6B7280)' }}
            tickLine={false}
            interval={6}
          />
          <YAxis
            reversed
            domain={[1, 30]}
            tick={{ fontSize: 11, fill: 'var(--color-muted-foreground, #6B7280)' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `#${v}`}
          />
          <Tooltip
            formatter={(value, name) => [`#${value}`, name]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid var(--border)' }}
          />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
          {rankKeywords.map(({ key, color }) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── White-label report block ──────────────────────────────────────────────────

function WhiteLabelReport() {
  const handlePrint = () => window.print()

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-foreground">White-Label Report</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Preview how a branded client report would look.</p>
        </div>
        <button
          onClick={handlePrint}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <PrinterIcon className="w-4 h-4" />
          Export PDF (print)
        </button>
      </div>

      {/* Report card */}
      <div className="p-5">
        <div className="border-2 border-dashed border-border rounded-xl p-6 space-y-5">
          {/* Agency header */}
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-muted border-2 border-dashed border-border flex items-center justify-center text-muted-foreground text-xs text-center leading-tight px-1">
                Logo
              </div>
              <div>
                <p className="font-bold text-foreground">Your Agency Name</p>
                <p className="text-xs text-muted-foreground">yoursite.com</p>
              </div>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Monthly SEO Report</p>
              <p>June 2026</p>
            </div>
          </div>

          <hr className="border-border" />

          {/* Summary numbers */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Performance Summary</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Total Clicks',    value: fmt(gscSummary.clicks) },
                { label: 'Impressions',     value: fmt(gscSummary.impressions) },
                { label: 'Avg. Position',   value: gscSummary.avgPosition },
                { label: 'Organic Sessions',value: fmt(ga4Summary.sessions) },
              ].map(({ label, value }) => (
                <div key={label} className="bg-muted/40 rounded-lg p-3 text-center">
                  <p className="text-xl font-bold text-foreground">{value}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Top keywords excerpt */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Top Ranking Keywords</p>
            <div className="space-y-1.5">
              {keywords.slice(0, 5).map((kw) => (
                <div key={kw.keyword} className="flex items-center justify-between gap-2 text-sm">
                  <span className="text-foreground truncate">{kw.keyword}</span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <ChangePill change={kw.change} />
                    <span className="font-semibold text-foreground w-6 text-right">#{kw.position}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-1 text-[11px] text-muted-foreground border-t border-border">
            Data sourced via Google Search Console &amp; GA4 · Prepared by Your Agency Name · Confidential
          </div>
        </div>
      </div>
    </div>
  )
}

// ── GSC connection card ───────────────────────────────────────────────────────

function GscConnectionCard() {
  const [status, setStatus] = useState(null) // null = loading
  const [flash, setFlash]   = useState(null) // { type: 'success'|'error', msg }
  const [busy, setBusy]     = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await client.get('/seo/gsc/status')
      setStatus(data)
    } catch {
      setStatus({ connected: false })
    }
  }, [])

  useEffect(() => {
    // Handle OAuth redirect params
    const params = new URLSearchParams(window.location.search)
    if (params.get('gsc_connected') === '1') {
      setFlash({ type: 'success', msg: 'Google Search Console connected successfully.' })
      window.history.replaceState({}, '', window.location.pathname)
    } else if (params.get('gsc_error')) {
      setFlash({ type: 'error', msg: `Connection failed: ${params.get('gsc_error').replace(/_/g, ' ')}.` })
      window.history.replaceState({}, '', window.location.pathname)
    }
    fetchStatus()
  }, [fetchStatus])

  const handleConnect = async () => {
    setBusy(true)
    try {
      const { data } = await client.get('/seo/gsc/connect')
      window.location.href = data.url
    } catch (err) {
      const msg = err?.response?.data?.detail ?? 'Could not start OAuth flow.'
      setFlash({ type: 'error', msg })
      setBusy(false)
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect Google Search Console? This will revoke the access token.')) return
    setBusy(true)
    try {
      await client.post('/seo/gsc/disconnect')
      setFlash({ type: 'success', msg: 'Disconnected.' })
      setStatus({ connected: false })
    } catch (err) {
      const msg = err?.response?.data?.detail ?? 'Disconnect failed.'
      setFlash({ type: 'error', msg })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-card border border-border rounded-xl p-5 flex flex-col gap-3">
      {flash && (
        <div className={`flex items-start gap-2 px-3 py-2.5 rounded-lg text-sm ${
          flash.type === 'success'
            ? 'bg-emerald-50 border border-emerald-200 text-emerald-800 dark:bg-emerald-900/20 dark:border-emerald-800 dark:text-emerald-300'
            : 'bg-red-50 border border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300'
        }`}>
          {flash.type === 'success'
            ? <CheckCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
            : <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />}
          <span>{flash.msg}</span>
          <button onClick={() => setFlash(null)} className="ml-auto text-inherit opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <LinkIcon className="w-4 h-4 text-muted-foreground" />
          <p className="text-sm font-semibold text-foreground">Google Search Console</p>
          {status === null && (
            <span className="text-xs text-muted-foreground animate-pulse">Checking…</span>
          )}
          {status?.connected && (
            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
              Connected
            </span>
          )}
          {status && !status.connected && (
            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-muted text-muted-foreground">
              Not connected
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {status?.connected ? (
            <button
              onClick={handleDisconnect}
              disabled={busy}
              className="px-3 py-1.5 rounded-lg border border-border text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors disabled:opacity-50"
            >
              Disconnect
            </button>
          ) : (
            <button
              onClick={handleConnect}
              disabled={busy || status === null}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold transition-colors disabled:opacity-50"
            >
              <LinkIcon className="w-4 h-4" />
              {busy ? 'Redirecting…' : 'Connect Google Search Console'}
            </button>
          )}
        </div>
      </div>

      {status?.connected && status?.property_url && (
        <p className="text-xs text-muted-foreground">
          Property: <span className="font-medium text-foreground">{status.property_url}</span>
          {status.connected_by && <> · Connected by <span className="font-medium text-foreground">{status.connected_by}</span></>}
        </p>
      )}
      {status?.connected && !status?.property_url && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Connected — no property selected yet. Use the API to set a property URL.
        </p>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SeoDashboardPage() {
  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-foreground">SEO Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Search performance, keyword rankings, and client reporting.</p>
        </div>
      </div>

      {/* GSC connection status */}
      <GscConnectionCard />

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <KpiCard
          title="Google Search Console"
          badge="Last 30 days"
          metrics={[
            { label: 'Total Clicks',    value: fmt(gscSummary.clicks) },
            { label: 'Impressions',     value: fmt(gscSummary.impressions) },
            { label: 'CTR',             value: `${gscSummary.ctr}%` },
            { label: 'Avg. Position',   value: `#${gscSummary.avgPosition}` },
          ]}
          sparkline={gscSummary.sparkline}
          sparkColor="#F59E0B"
        />
        <KpiCard
          title="Google Analytics 4"
          badge="Last 30 days"
          metrics={[
            { label: 'Sessions',          value: fmt(ga4Summary.sessions) },
            { label: 'Users',             value: fmt(ga4Summary.users) },
            { label: 'Engagement Rate',   value: `${ga4Summary.engagementRate}%` },
            { label: 'Avg. per Session',  value: (ga4Summary.sessions / 30).toFixed(0) + '/day' },
          ]}
          sparkline={ga4Summary.sparkline}
          sparkColor="#0EA5E9"
        />
      </div>

      {/* Rank trend chart */}
      <RankChart />

      {/* Keywords table */}
      <KeywordsTable />

      {/* White-label report */}
      <WhiteLabelReport />
    </div>
  )
}

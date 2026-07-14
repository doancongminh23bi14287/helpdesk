import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Brush,
} from 'recharts'
import { ArrowUpIcon, ArrowDownIcon, MinusIcon, PrinterIcon, LinkIcon, CheckCircleIcon, ExclamationCircleIcon, ArrowsPointingOutIcon, ChartBarIcon } from '@heroicons/react/24/outline'
import TrendSparkline from '@/components/seo/TrendSparkline'
import { useGscData } from '@/hooks/useGscData'
import client from '@/api/client'
import { fillDailyTrend } from '@/lib/seoTrend'
import { Button, EmptyState, MobileCardList, MobileDataCard, MobileDataRow, Modal, PageHeader, ResponsiveTableViewport } from '@/components/ui'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

// ── Banners ───────────────────────────────────────────────────────────────────

function LiveBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
      Live GSC data
    </span>
  )
}

// ── KPI card ─────────────────────────────────────────────────────────────────

function KpiCard({ title, badge, metrics, trend, sparkColor, trendLabel, isLoading, error }) {
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
      <TrendSparkline data={trend} color={sparkColor} valueLabel={trendLabel} isLoading={isLoading} error={error} />
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

function KeywordsTable({ keywords }) {
  if (!keywords || keywords.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card">
        <EmptyState
          icon={ChartBarIcon}
          title="No keyword data yet"
          description="Google Search Console needs more time to accumulate keyword performance data."
        />
      </div>
    )
  }

  const mobileCards = (
    <MobileCardList ariaLabel="Tracked keywords">
      {keywords.map((row) => (
        <MobileDataCard key={row.keyword}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-foreground">{row.keyword}</p>
              <p className="mt-1 break-all text-xs text-muted-foreground">{row.url || 'No landing page'}</p>
            </div>
            <span className={
              'inline-flex h-9 min-w-9 flex-none items-center justify-center rounded-lg px-2 text-sm font-bold ' +
              (row.position <= 3
                ? 'bg-success-muted text-success'
                : row.position <= 10
                  ? 'bg-warning-muted text-warning'
                  : 'bg-muted text-muted-foreground')
            }>
              #{row.position}
            </span>
          </div>
          <dl className="mt-3 border-t border-border pt-2">
            <MobileDataRow label="Change"><ChangePill change={row.change} /></MobileDataRow>
            <MobileDataRow label="Volume">{row.volume.toLocaleString()}</MobileDataRow>
          </dl>
        </MobileDataCard>
      ))}
    </MobileCardList>
  )

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="border-b border-border px-4 py-4 sm:px-5">
        <h2 className="text-sm font-semibold text-foreground">Tracked Keywords</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Position as of today vs. 30 days ago</p>
      </div>
      <ResponsiveTableViewport mobile={mobileCards}>
        <table className="w-full min-w-[560px] text-sm">
          <thead className="bg-muted/30">
            <tr className="border-b border-border">
              <th className="sticky top-0 text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase">Keyword</th>
              <th className="text-center px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Pos.</th>
              <th className="text-center px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Change</th>
              <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Volume</th>
              <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase">URL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {keywords.map((row) => (
              <tr key={row.keyword} className="transition-colors hover:bg-muted/20">
                <td className="px-5 py-3 font-medium text-foreground">{row.keyword}</td>
                <td className="px-4 py-3 text-center">
                  <span className={
                    'inline-flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold ' +
                    (row.position <= 3
                      ? 'bg-success-muted text-success'
                      : row.position <= 10
                        ? 'bg-warning-muted text-warning'
                        : 'bg-muted text-muted-foreground')
                  }>
                    {row.position}
                  </span>
                </td>
                <td className="px-4 py-3 text-center"><ChangePill change={row.change} /></td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{row.volume.toLocaleString()}</td>
                <td className="max-w-[180px] truncate px-5 py-3 text-xs text-muted-foreground">{row.url}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ResponsiveTableViewport>
    </div>
  )
}

// ── Rank history chart ────────────────────────────────────────────────────────

function RankChartCanvas({ rankHistory, rankKeywords, isClicksChart, height, showBrush = false }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rankHistory} margin={{ top: 16, right: 16, left: -8, bottom: showBrush ? 8 : 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: 'hsl(var(--text-muted))' }}
          tickLine={false}
          minTickGap={24}
        />
        <YAxis
          reversed={!isClicksChart}
          domain={isClicksChart ? ['auto', 'auto'] : [1, 30]}
          tick={{ fontSize: 11, fill: 'hsl(var(--text-muted))' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => isClicksChart ? fmt(value) : '#' + value}
        />
        <Tooltip
          formatter={(value, name) => [isClicksChart ? fmt(value) : '#' + value, name]}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid hsl(var(--border))' }}
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
        {showBrush && (
          <Brush
            dataKey="date"
            height={28}
            travellerWidth={10}
            stroke="hsl(var(--info))"
            fill="hsl(var(--surface-muted))"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  )
}

function RankChart({ rankHistory, rankKeywords, usingRealData }) {
  const [expanded, setExpanded] = useState(false)
  const isClicksChart = usingRealData && rankKeywords?.length === 1 && rankKeywords[0].key === 'clicks'

  if (!rankHistory || rankHistory.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card">
        <EmptyState
          icon={ChartBarIcon}
          title="No ranking history"
          description="Ranking and click trends will appear after Search Console returns daily data."
        />
      </div>
    )
  }

  return (
    <>
      <section className="rounded-xl border border-border bg-card p-4 sm:p-5">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              {isClicksChart ? 'Clicks Over Time' : 'Keyword Rankings Over Time'}
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {isClicksChart
                ? 'Daily clicks from Google Search Console.'
                : 'Lower position means a better rank. Improvements move upward.'}
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => setExpanded(true)} aria-label="Open chart fullscreen">
            <ArrowsPointingOutIcon className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline">Expand</span>
          </Button>
        </div>
        <div
          role="button"
          tabIndex={0}
          aria-label="Open chart fullscreen"
          onClick={() => setExpanded(true)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              setExpanded(true)
            }
          }}
          className="h-[340px] min-w-0 cursor-zoom-in rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:h-[380px]"
        >
          <RankChartCanvas
            rankHistory={rankHistory}
            rankKeywords={rankKeywords}
            isClicksChart={isClicksChart}
            height="100%"
          />
        </div>
      </section>

      <Modal
        open={expanded}
        onClose={() => setExpanded(false)}
        title={isClicksChart ? 'Clicks Over Time' : 'Keyword Rankings Over Time'}
        description="Drag the range selector below the chart to zoom into a date range."
        size="full"
      >
        <div className="h-[calc(100dvh-11rem)] min-h-[360px] w-full">
          <RankChartCanvas
            rankHistory={rankHistory}
            rankKeywords={rankKeywords}
            isClicksChart={isClicksChart}
            height="100%"
            showBrush
          />
        </div>
      </Modal>
    </>
  )
}

// ── White-label report block ──────────────────────────────────────────────────

function WhiteLabelReport({ ga4Summary, gscSummary, keywords }) {
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
  const [properties, setProperties] = useState([])
  const [selectingProperty, setSelectingProperty] = useState(false)

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
      if (data.error) {
        setFlash({ type: 'error', msg: data.detail || 'GSC is not configured.' })
        setBusy(false)
        return
      }
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
      await client.delete('/seo/gsc/disconnect')
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
          {status && !status.connected && status.configured && (
            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-muted text-muted-foreground">
              Not connected
            </span>
          )}
          {status && !status.connected && status.configured === false && (
            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
              Chưa kết nối (cấu hình ở production)
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
              disabled={busy || status === null || status?.configured === false}
              title={status?.configured === false ? 'Cần cấu hình GSC_CLIENT_ID / GSC_CLIENT_SECRET trên server' : undefined}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
        <div className="flex flex-col gap-2">
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Connected — chưa chọn property. Chọn website bên dưới:
          </p>
          {properties.length === 0 && (
            <button
              onClick={async () => {
                try {
                  const { data } = await client.get('/seo/gsc/properties')
                  setProperties(data.properties || [])
                } catch (err) {
                  setFlash({ type: 'error', msg: 'Không lấy được danh sách property.' })
                }
              }}
              className="text-xs px-3 py-1.5 rounded-lg border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 w-fit"
            >
              Xem danh sách property
            </button>
          )}
          {properties.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <select
                className="text-xs border border-border rounded-md px-2 py-1.5 bg-background text-foreground"
                defaultValue=""
                onChange={async (e) => {
                  if (!e.target.value) return
                  setSelectingProperty(true)
                  try {
                    await client.post('/seo/gsc/property', { property_url: e.target.value })
                    setFlash({ type: 'success', msg: `Property đã chọn: ${e.target.value}` })
                    fetchStatus()
                    setProperties([])
                  } catch (err) {
                    setFlash({ type: 'error', msg: 'Không chọn được property.' })
                  } finally {
                    setSelectingProperty(false)
                  }
                }}
                disabled={selectingProperty}
              >
                <option value="">-- Chọn property --</option>
                {properties.map(p => (
                  <option key={p.siteUrl} value={p.siteUrl}>{p.siteUrl}</option>
                ))}
              </select>
              {selectingProperty && <span className="text-xs text-muted-foreground animate-pulse">Đang lưu…</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── GA4 connection card ───────────────────────────────────────────────────────

function Ga4ConnectionCard({ onReportStateChange }) {
  const [status, setStatus]     = useState(null)
  const [flash, setFlash]       = useState(null)
  const [busy, setBusy]         = useState(false)
  const [properties, setProperties] = useState([])
  const [selectingProperty, setSelectingProperty] = useState(false)

  const fetchStatus = useCallback(async () => {
    onReportStateChange({ report: null, isLoading: true, error: null })
    try {
      const { data } = await client.get('/seo/ga4/status')
      setStatus(data)
      if (data.connected && data.property_id) {
        try {
          const { data: report } = await client.get('/seo/ga4/report')
          onReportStateChange({ report, isLoading: false, error: null })
        } catch (err) {
          onReportStateChange({
            report: null,
            isLoading: false,
            error: err?.message ?? 'Không thể tải dữ liệu GA4',
          })
        }
      } else {
        onReportStateChange({ report: null, isLoading: false, error: null })
      }
    } catch (err) {
      setStatus({ connected: false })
      onReportStateChange({
        report: null,
        isLoading: false,
        error: err?.message ?? 'Không thể kiểm tra kết nối GA4',
      })
    }
  }, [onReportStateChange])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('ga4_connected') === '1') {
      setFlash({ type: 'success', msg: 'Google Analytics 4 connected.' })
      window.history.replaceState({}, '', window.location.pathname)
    } else if (params.get('ga4_error')) {
      setFlash({ type: 'error', msg: `GA4 connection failed: ${params.get('ga4_error').replace(/_/g, ' ')}.` })
      window.history.replaceState({}, '', window.location.pathname)
    }
    fetchStatus()
  }, [fetchStatus])

  const handleConnect = async () => {
    setBusy(true)
    try {
      const { data } = await client.get('/seo/ga4/connect')
      if (data.error) {
        setFlash({ type: 'error', msg: data.detail || 'GA4 is not configured.' })
        setBusy(false)
        return
      }
      window.location.href = data.url
    } catch (err) {
      setFlash({ type: 'error', msg: err?.response?.data?.detail ?? 'Could not start GA4 OAuth flow.' })
      setBusy(false)
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect Google Analytics 4?')) return
    setBusy(true)
    try {
      await client.delete('/seo/ga4/disconnect')
      setFlash({ type: 'success', msg: 'GA4 disconnected.' })
      setStatus({ connected: false })
      onReportStateChange({ report: null, isLoading: false, error: null })
    } catch (err) {
      setFlash({ type: 'error', msg: err?.response?.data?.detail ?? 'Disconnect failed.' })
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
          <p className="text-sm font-semibold text-foreground">Google Analytics 4</p>
          {status === null && <span className="text-xs text-muted-foreground animate-pulse">Checking…</span>}
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
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <LinkIcon className="w-4 h-4" />
              {busy ? 'Redirecting…' : 'Connect Google Analytics 4'}
            </button>
          )}
        </div>
      </div>

      {status?.connected && status?.property_name && (
        <p className="text-xs text-muted-foreground">
          Property: <span className="font-medium text-foreground">{status.property_name}</span>
          {status.property_id && <> · ID: {status.property_id}</>}
        </p>
      )}

      {status?.connected && !status?.property_id && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Connected — chưa chọn property. Chọn bên dưới:
          </p>
          {properties.length === 0 && (
            <button
              onClick={async () => {
                try {
                  const { data } = await client.get('/seo/ga4/properties')
                  setProperties(data.properties || [])
                } catch {
                  setFlash({ type: 'error', msg: 'Không lấy được danh sách property.' })
                }
              }}
              className="text-xs px-3 py-1.5 rounded-lg border border-sky-300 bg-sky-50 text-sky-700 hover:bg-sky-100 w-fit"
            >
              Xem danh sách property
            </button>
          )}
          {properties.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <select
                className="text-xs border border-border rounded-md px-2 py-1.5 bg-background text-foreground"
                defaultValue=""
                onChange={async (e) => {
                  if (!e.target.value) return
                  const selected = properties.find(p => p.property === e.target.value)
                  setSelectingProperty(true)
                  try {
                    await client.post('/seo/ga4/property', {
                      property_id: e.target.value,
                      property_name: selected?.displayName ?? '',
                    })
                    setFlash({ type: 'success', msg: `Property đã chọn: ${selected?.displayName ?? e.target.value}` })
                    fetchStatus()
                    setProperties([])
                  } catch {
                    setFlash({ type: 'error', msg: 'Không chọn được property.' })
                  } finally {
                    setSelectingProperty(false)
                  }
                }}
                disabled={selectingProperty}
              >
                <option value="">-- Chọn property --</option>
                {properties.map(p => (
                  <option key={p.property} value={p.property}>
                    {p.displayName} ({p.property})
                  </option>
                ))}
              </select>
              {selectingProperty && <span className="text-xs text-muted-foreground animate-pulse">Đang lưu…</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SeoDashboardPage() {
  const {
    isLoading: isGscLoading,
    error: gscError,
    usingRealData,
    keywords,
    rankHistory,
    rankKeywords,
    gscSummary,
  } = useGscData()
  const [ga4ReportState, setGa4ReportState] = useState({
    report: null,
    isLoading: true,
    error: null,
  })
  const [trendEndDate] = useState(() => new Date())

  const { report: ga4Report, isLoading: isGa4Loading, error: ga4Error } = ga4ReportState
  const ga4Summary = ga4Report?.summary ?? {
    sessions: 0,
    users: 0,
    engagementRate: 0,
    avgSessionDuration: 0,
  }
  const gscTrend = fillDailyTrend(gscSummary.trend, { endDate: trendEndDate })
  const ga4DailyRows = ga4Report?.trend ?? ga4Report?.sparkline ?? []
  const ga4Trend = fillDailyTrend(ga4DailyRows, { endDate: trendEndDate })

  const hasData = keywords && keywords.length > 0

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto space-y-5">
      <PageHeader
        title="SEO Dashboard"
        description="Search performance, keyword rankings, and client reporting."
        metadata={usingRealData && hasData ? <LiveBadge /> : null}
      />

      {/* Connection cards */}
      <GscConnectionCard />
      <Ga4ConnectionCard onReportStateChange={setGa4ReportState} />

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <KpiCard
          title="Google Search Console"
          badge="Last 30 days"
          metrics={[
            { label: 'Total Clicks',    value: fmt(gscSummary.clicks) },
            { label: 'Impressions',     value: fmt(gscSummary.impressions) },
            { label: 'CTR',             value: `${gscSummary.ctr}%` },
            { label: 'Avg. Position',   value: gscSummary.avgPosition ? `#${gscSummary.avgPosition}` : '—' },
          ]}
          trend={gscTrend}
          sparkColor="#F59E0B"
          trendLabel="Clicks"
          isLoading={isGscLoading}
          error={gscError}
        />
        <KpiCard
          title="Google Analytics 4"
          badge={ga4Report ? 'Live · Last 30 days' : 'Last 30 days'}
          metrics={[
            { label: 'Sessions',         value: fmt(ga4Summary.sessions) },
            { label: 'Users',            value: fmt(ga4Summary.users) },
            { label: 'Engagement Rate',  value: `${ga4Summary.engagementRate}%` },
            { label: 'Avg. per Session', value: Math.round(ga4Summary.sessions / 30) + '/day' },
          ]}
          trend={ga4Trend}
          sparkColor="#0EA5E9"
          trendLabel="Sessions"
          isLoading={isGa4Loading}
          error={ga4Error}
        />
      </div>

      {/* Rank trend chart */}
      <RankChart rankHistory={rankHistory} rankKeywords={rankKeywords} usingRealData={usingRealData} />

      {/* Keywords table */}
      <KeywordsTable keywords={keywords} />

      {/* White-label report */}
      <WhiteLabelReport ga4Summary={ga4Summary} gscSummary={gscSummary} keywords={keywords} />
    </div>
  )
}

import { useState, useEffect } from 'react'
import client from '@/api/client'
import { normalizeTrendData } from '@/lib/seoTrend'

function emptyGscData() {
  return {
    keywords: [],
    rankHistory: [],
    rankKeywords: [],
    gscSummary: { clicks: 0, impressions: 0, ctr: 0, avgPosition: 0, trend: [] },
  }
}

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function mapQueryRows(rows) {
  if (!rows || rows.length === 0) return []
  return rows.map((row) => ({
    keyword:      row.keys?.[0] ?? '',
    position:     Math.round(toNumber(row.position) || 99),
    prevPosition: Math.round(toNumber(row.position) || 99),
    change:       0,
    volume:       toNumber(row.impressions),
    url:          row.keys?.[1] ?? '',
  }))
}

function mapDateRows(rows) {
  if (!rows || rows.length === 0) return []
  return rows
    .map((row) => ({
      date:        typeof row.keys?.[0] === 'string' ? row.keys[0] : '',
      clicks:      toNumber(row.clicks),
      impressions: toNumber(row.impressions),
      position:    toNumber(row.position),
    }))
    .filter(({ date }) => date)
    .sort((a, b) => a.date.localeCompare(b.date))
}

function mapSummary(current, dateRows) {
  const trend = normalizeTrendData(
    (dateRows ?? []).map(({ date, clicks }) => ({ date, value: clicks })),
  )
  return {
    clicks: toNumber(current?.clicks),
    impressions: toNumber(current?.impressions),
    ctr: Number((toNumber(current?.ctr) * 100).toFixed(2)),
    avgPosition: Number(toNumber(current?.average_position).toFixed(1)),
    trend,
  }
}

export function useGscData() {
  const [isLoading,    setIsLoading]    = useState(true)
  const [isConnected,  setIsConnected]  = useState(false)
  const [usingRealData, setUsingRealData] = useState(false)
  const [error,        setError]        = useState(null)
  const [gscData,      setGscData]      = useState(emptyGscData)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setIsLoading(true)
      setError(null)
      try {
        const statusRes = await client.get('/seo/gsc/status')
        const status = statusRes.data
        if (cancelled) return

        if (!status.connected) {
          setIsConnected(false)
          setUsingRealData(false)
          setGscData(emptyGscData())
          return
        }

        setIsConnected(true)

        const dashboardRes = await client.get('/seo/gsc/dashboard', { params: { period: 28 } })
        if (cancelled) return
        const dashboard = dashboardRes.data ?? {}
        const current = dashboard.current || {}
        const queryRows = dashboard.top_queries || []
        const dateRows = mapDateRows(dashboard.daily)
        const mappedKeywords = mapQueryRows(queryRows)
        setUsingRealData(true)
        setGscData({
          keywords: mappedKeywords,
          rankHistory: dateRows.map(({ date, clicks }) => ({ date, clicks })),
          rankKeywords: [{ key: 'clicks', color: '#F59E0B' }],
          gscSummary: mapSummary(current, dateRows),
        })
      } catch (err) {
        if (cancelled) return
        setError(err?.message ?? 'Unknown error')
        setUsingRealData(false)
        setGscData(emptyGscData())
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  return { isConnected, isLoading, error, usingRealData, ...gscData }
}

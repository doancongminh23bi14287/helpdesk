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

function toYYYYMMDD(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
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

function buildSummary(queryRows, dateRows) {
  const rows = queryRows ?? []
  const totalClicks      = rows.reduce((sum, row) => sum + toNumber(row.clicks), 0)
  const totalImpressions = rows.reduce((sum, row) => sum + toNumber(row.impressions), 0)
  const avgCtr           = totalImpressions > 0 ? ((totalClicks / totalImpressions) * 100).toFixed(2) : 0
  const avgPosition      = rows.length > 0
    ? (rows.reduce((sum, row) => sum + toNumber(row.position), 0) / rows.length).toFixed(1)
    : 0
  const trend = normalizeTrendData(
    (dateRows ?? []).map(({ date, clicks }) => ({ date, value: clicks })),
  )
  return { clicks: totalClicks, impressions: totalImpressions, ctr: Number(avgCtr), avgPosition: Number(avgPosition), trend }
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

        const today = new Date()
        const start = new Date(today)
        start.setDate(today.getDate() - 29)
        const startStr = toYYYYMMDD(start)
        const endStr   = toYYYYMMDD(today)

        const [queryRes, dateRes] = await Promise.all([
          client.get('/seo/gsc/search-analytics', { params: { start_date: startStr, end_date: endStr, dimensions: 'query', row_limit: 10 } }),
          client.get('/seo/gsc/search-analytics', { params: { start_date: startStr, end_date: endStr, dimensions: 'date',  row_limit: 30 } }),
        ])
        if (cancelled) return

        const queryRows = queryRes.data?.rows ?? []
        const dateRows  = dateRes.data?.rows  ?? []

        const mappedKeywords = mapQueryRows(queryRows)
        const mappedDateRows  = mapDateRows(dateRows)
        const summary         = buildSummary(queryRows, mappedDateRows)

        // Build a simple date-based rank history for the line chart using clicks as proxy
        const dateRankHistory = mappedDateRows.map((r) => ({ date: r.date, clicks: r.clicks }))

        setUsingRealData(true)
        setGscData({
          keywords:     mappedKeywords,
          rankHistory:  dateRankHistory,
          rankKeywords: [{ key: 'clicks', color: '#F59E0B' }],
          gscSummary:   summary,
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

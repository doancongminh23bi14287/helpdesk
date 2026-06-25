import { useState, useEffect } from 'react'
import client from '@/api/client'
import { keywords as mockKeywords, rankHistory as mockRankHistory, rankKeywords as mockRankKeywords, gscSummary as mockGscSummary } from '@/data/seoMockData'

function toYYYYMMDD(date) {
  return date.toISOString().slice(0, 10)
}

function mapQueryRows(rows) {
  if (!rows || rows.length === 0) return []
  return rows.map((row) => ({
    keyword:      row.keys?.[0] ?? '',
    position:     Math.round(row.position ?? 99),
    prevPosition: Math.round(row.position ?? 99),
    change:       0,
    volume:       row.impressions ?? 0,
    url:          row.keys?.[1] ?? '',
  }))
}

function mapDateRows(rows) {
  if (!rows || rows.length === 0) return []
  return rows.map((row) => ({
    date:        row.keys?.[0] ?? '',
    clicks:      row.clicks ?? 0,
    impressions: row.impressions ?? 0,
    position:    row.position ?? 0,
  }))
}

function buildSummary(queryRows, dateRows) {
  if (!queryRows || queryRows.length === 0) {
    return { clicks: 0, impressions: 0, ctr: 0, avgPosition: 0, sparkline: [] }
  }
  const totalClicks      = queryRows.reduce((s, r) => s + (r.clicks ?? 0), 0)
  const totalImpressions = queryRows.reduce((s, r) => s + (r.impressions ?? 0), 0)
  const avgCtr           = totalImpressions > 0 ? ((totalClicks / totalImpressions) * 100).toFixed(2) : 0
  const avgPosition      = queryRows.length > 0
    ? (queryRows.reduce((s, r) => s + (r.position ?? 0), 0) / queryRows.length).toFixed(1)
    : 0
  const sparkline = dateRows && dateRows.length > 0
    ? dateRows.map((r) => r.clicks)
    : []
  return { clicks: totalClicks, impressions: totalImpressions, ctr: Number(avgCtr), avgPosition: Number(avgPosition), sparkline }
}

export function useGscData() {
  const [isLoading,    setIsLoading]    = useState(true)
  const [isConnected,  setIsConnected]  = useState(false)
  const [usingRealData, setUsingRealData] = useState(false)
  const [error,        setError]        = useState(null)
  const [gscData,      setGscData]      = useState({
    keywords:    mockKeywords,
    rankHistory: mockRankHistory,
    rankKeywords: mockRankKeywords,
    gscSummary:  mockGscSummary,
  })

  useEffect(() => {
    let cancelled = false

    async function load() {
      setIsLoading(true)
      try {
        const statusRes = await client.get('/seo/gsc/status')
        const status = statusRes.data
        if (cancelled) return

        if (!status.connected) {
          setIsConnected(false)
          setUsingRealData(false)
          setGscData({ keywords: mockKeywords, rankHistory: mockRankHistory, rankKeywords: mockRankKeywords, gscSummary: mockGscSummary })
          return
        }

        setIsConnected(true)

        const today = new Date()
        const start = new Date(today)
        start.setDate(today.getDate() - 30)
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
        console.warn('[useGscData] API error, falling back to mock data:', err?.message)
        setError(err?.message ?? 'Unknown error')
        setUsingRealData(false)
        setGscData({ keywords: mockKeywords, rankHistory: mockRankHistory, rankKeywords: mockRankKeywords, gscSummary: mockGscSummary })
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  return { isConnected, isLoading, error, usingRealData, ...gscData }
}

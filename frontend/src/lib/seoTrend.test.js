import { describe, expect, it } from 'vitest'
import { fillDailyTrend, getTrendDomain, getTrendState, normalizeTrendData } from './seoTrend'

describe('normalizeTrendData', () => {
  it('parses values, preserves zeroes, sorts dates, and does not mutate the source', () => {
    const source = [
      { date: '2026-07-03', value: '7' },
      { date: '2026-07-01', value: 0 },
      { date: '2026-07-02', value: null },
    ]
    const snapshot = structuredClone(source)

    expect(normalizeTrendData(source)).toEqual([
      { date: '2026-07-01', value: 0 },
      { date: '2026-07-02', value: 0 },
      { date: '2026-07-03', value: 7 },
    ])
    expect(source).toEqual(snapshot)
  })

  it('drops rows without a date and converts invalid or missing metrics to zero', () => {
    expect(normalizeTrendData([
      { date: '', value: 10 },
      { value: 3 },
      { date: '2026-07-02', value: undefined },
      { date: '2026-07-01', value: 'not-a-number' },
    ])).toEqual([
      { date: '2026-07-01', value: 0 },
      { date: '2026-07-02', value: 0 },
    ])
  })

  it('accepts the legacy GA4 v field while the running backend is upgraded', () => {
    expect(normalizeTrendData([
      { date: '2026-07-01', v: '9' },
    ])).toEqual([
      { date: '2026-07-01', value: 9 },
    ])
  })

  it('returns an empty series for non-array API payloads', () => {
    expect(normalizeTrendData(null)).toEqual([])
    expect(normalizeTrendData({ rows: [] })).toEqual([])
  })
})

describe('fillDailyTrend', () => {
  it('fills missing GA4 dates with zero once at least one real row exists', () => {
    expect(fillDailyTrend(
      [{ date: '2026-07-02', v: '5' }],
      { days: 4, endDate: new Date(2026, 6, 4) },
    )).toEqual([
      { date: '2026-07-01', value: 0 },
      { date: '2026-07-02', value: 5 },
      { date: '2026-07-03', value: 0 },
      { date: '2026-07-04', value: 0 },
    ])
  })

  it('uses identical date boundaries for GSC and GA4 with the same end date', () => {
    const endDate = new Date(2026, 6, 14)
    const gsc = fillDailyTrend([{ date: '2026-07-01', value: 2 }], { days: 30, endDate })
    const ga4 = fillDailyTrend([{ date: '2026-06-28', value: 5 }], { days: 30, endDate })

    expect(gsc.map(({ date }) => date)).toEqual(ga4.map(({ date }) => date))
    expect(gsc[0].date).toBe('2026-06-15')
    expect(gsc.at(-1).date).toBe('2026-07-14')
  })

  it('keeps a completely empty API response empty', () => {
    expect(fillDailyTrend([], { days: 30 })).toEqual([])
  })
})

describe('getTrendDomain', () => {
  it('centers an all-zero series instead of pinning it to the bottom', () => {
    expect(getTrendDomain([
      { date: '2026-07-01', value: 0 },
      { date: '2026-07-02', value: 0 },
    ])).toEqual([-1, 1])
  })

  it('adds data-driven padding for a varying series', () => {
    expect(getTrendDomain([
      { date: '2026-07-01', value: 10 },
      { date: '2026-07-02', value: 20 },
    ])).toEqual([8.8, 21.2])
  })
})

describe('getTrendState', () => {
  const point = { date: '2026-07-01', value: 1 }

  it('covers loading, API error, empty, one-point, and multi-point states', () => {
    expect(getTrendState([], { isLoading: true })).toBe('loading')
    expect(getTrendState([], { error: 'API failed' })).toBe('error')
    expect(getTrendState([])).toBe('empty')
    expect(getTrendState([point])).toBe('single')
    expect(getTrendState([point, { ...point, date: '2026-07-02' }])).toBe('ready')
  })
})

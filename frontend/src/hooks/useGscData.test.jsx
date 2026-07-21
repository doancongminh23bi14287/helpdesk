import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import client from '@/api/client'
import { useGscData } from './useGscData'

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('useGscData', () => {
  beforeEach(() => {
    client.get.mockReset()
  })

  it('maps and sorts daily clicks without losing zero-value days', async () => {
    client.get.mockImplementation((url) => {
      if (url === '/seo/gsc/status') {
        return Promise.resolve({ data: { connected: true } })
      }

      return Promise.resolve({
        data: {
          current: { clicks: 9, impressions: 45, ctr: 0.2, average_position: 4 },
          top_queries: [{
            keys: ['seo dashboard'], clicks: '7', impressions: '70', position: '3.5',
          }],
          daily: [
            { keys: ['2026-07-03'], clicks: '7', impressions: '20', position: '3' },
            { keys: ['2026-07-01'], clicks: 0, impressions: '10', position: '5' },
            { keys: ['2026-07-02'], clicks: '2', impressions: '15', position: '4' },
          ],
        },
      })
    })

    const { result } = renderHook(() => useGscData())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.gscSummary.trend).toEqual([
      { date: '2026-07-01', value: 0 },
      { date: '2026-07-02', value: 2 },
      { date: '2026-07-03', value: 7 },
    ])
    expect(result.current.rankHistory).toEqual([
      { date: '2026-07-01', clicks: 0 },
      { date: '2026-07-02', clicks: 2 },
      { date: '2026-07-03', clicks: 7 },
    ])

    expect(result.current.gscSummary).toMatchObject({
      clicks: 9, impressions: 45, ctr: 20, avgPosition: 4,
    })
    expect(client.get).toHaveBeenCalledWith('/seo/gsc/dashboard', { params: { period: 28 } })
  })

  it('keeps production data empty when GSC is disconnected', async () => {
    client.get.mockResolvedValueOnce({ data: { connected: false } })

    const { result } = renderHook(() => useGscData())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.usingRealData).toBe(false)
    expect(result.current.keywords).toEqual([])
    expect(result.current.rankHistory).toEqual([])
    expect(result.current.gscSummary.trend).toEqual([])
  })

  it('keeps production data empty and exposes the error when the API fails', async () => {
    client.get.mockRejectedValueOnce(new Error('GSC unavailable'))

    const { result } = renderHook(() => useGscData())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBe('GSC unavailable')
    expect(result.current.gscSummary).toEqual({
      clicks: 0,
      impressions: 0,
      ctr: 0,
      avgPosition: 0,
      trend: [],
    })
  })
})

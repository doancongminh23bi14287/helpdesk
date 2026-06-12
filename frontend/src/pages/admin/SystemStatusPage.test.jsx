import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import SystemStatusPage from './SystemStatusPage'

vi.mock('@/api/system', () => ({
  getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'CustomerHub API', version: '1.0.0' }),
  getReady: vi.fn().mockRejectedValue({
    response: {
      data: {
        status: 'degraded',
        checks: {
          database: 'ok',
          redis: 'error: Redis unreachable',
          email_outbox: 'warn: 3 pending',
        },
      },
    },
  }),
}))

describe('SystemStatusPage', () => {
  it('handles ready failure responses', async () => {
    render(<SystemStatusPage />)

    expect(await screen.findByText('System Status')).toBeInTheDocument()
    expect(await screen.findByText(/WorkDesk API/)).toBeInTheDocument()
    expect(await screen.findByText('degraded')).toBeInTheDocument()
    expect(screen.getByText('error: Redis unreachable')).toBeInTheDocument()
    expect(screen.getByText('warn: 3 pending')).toBeInTheDocument()
  })
})

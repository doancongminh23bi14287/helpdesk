import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import AccountSecurityPage from './AccountSecurityPage'

vi.mock('@/api/auth', () => ({
  listSessions: vi.fn().mockResolvedValue([
    {
      id: 1,
      ip_address: '127.0.0.1',
      user_agent: 'Chrome',
      created_at: '2026-06-08T10:00:00',
      expires_at: '2026-06-15T10:00:00',
      is_active: true,
      is_current: true,
    },
  ]),
  revokeSession: vi.fn(),
  logoutAllSessions: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  clearTokens: vi.fn(),
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ logout: vi.fn() }),
}))

describe('AccountSecurityPage', () => {
  it('renders active sessions', async () => {
    render(<AccountSecurityPage />)

    expect(await screen.findByText('Session #1')).toBeInTheDocument()
    expect(screen.getByText('Current')).toBeInTheDocument()
    expect(screen.getByText('Chrome')).toBeInTheDocument()
  })
})

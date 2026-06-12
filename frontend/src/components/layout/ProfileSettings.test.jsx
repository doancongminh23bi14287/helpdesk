import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProfileSettings from './ProfileSettings'

const logoutMock = vi.fn()
let mockUser = { full_name: 'Demo Admin', email: 'demo@test.com', avatar_color: 'blue', avatar_url: null }

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ user: mockUser, logout: logoutMock }),
}))

beforeEach(() => {
  logoutMock.mockReset()
  mockUser = { full_name: 'Demo Admin', email: 'demo@test.com', avatar_color: 'blue', avatar_url: null }
})

const wrap = (ui) => (
  <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    {ui}
  </MemoryRouter>
)

describe('ProfileSettings dropdown', () => {
  it('shows initials when no avatar_url is present', () => {
    render(wrap(<ProfileSettings />))
    // "Demo Admin" → DA
    expect(screen.getAllByText('DA').length).toBeGreaterThan(0)
  })

  it('opens the dropdown with profile/preferences/security links and logout', async () => {
    render(wrap(<ProfileSettings />))
    await userEvent.click(screen.getByRole('button', { name: /Open profile menu/i }))

    expect(screen.getByRole('menuitem', { name: /My Profile/i })).toHaveAttribute('href', '/profile')
    expect(screen.getByRole('menuitem', { name: /Preferences/i })).toHaveAttribute('href', '/preferences')
    expect(screen.getByRole('menuitem', { name: /Account Security/i })).toHaveAttribute('href', '/account/security')
    expect(screen.getByRole('menuitem', { name: /Sign Out/i })).toBeInTheDocument()
  })

  it('renders an image instead of initials when avatar_url is set', () => {
    mockUser = { ...mockUser, avatar_url: '/api/auth/avatars/1/abc.png?v=1' }
    render(wrap(<ProfileSettings />))
    const imgs = screen.getAllByRole('img')
    expect(imgs.length).toBeGreaterThan(0)
    expect(imgs[0].getAttribute('src')).toContain('/api/auth/avatars/1/abc.png?v=1')
  })
})

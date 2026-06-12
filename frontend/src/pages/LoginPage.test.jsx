import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LoginPage from './LoginPage'

const navigate = vi.fn()
const loginMock = vi.fn()
const checkSessionMock = vi.fn()
const RouterWrapper = ({ children }) => (
  <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    {children}
  </MemoryRouter>
)

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

vi.mock('@/api/auth', () => ({
  login: (...args) => loginMock(...args),
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ checkSession: checkSessionMock }),
}))

describe('LoginPage', () => {
  beforeEach(() => {
    navigate.mockReset()
    loginMock.mockResolvedValue({})
    checkSessionMock.mockResolvedValue(true)
  })

  it('renders and submits credentials', async () => {
    render(<LoginPage />, { wrapper: RouterWrapper })

    await userEvent.type(screen.getByPlaceholderText('you@company.com'), 'user@example.com')
    await userEvent.type(screen.getByPlaceholderText('••••••••'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(loginMock).toHaveBeenCalledWith('user@example.com', 'secret')
    expect(checkSessionMock).toHaveBeenCalled()
    expect(navigate).toHaveBeenCalledWith('/')
  })
})

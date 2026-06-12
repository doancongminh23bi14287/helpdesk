import { describe, expect, it, vi } from 'vitest'

const apiLogout = vi.fn()
const clearTokens = vi.fn()

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  logout: () => apiLogout(),
  getMe: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  clearTokens: () => clearTokens(),
}))

describe('useAuthStore', () => {
  it('clears auth state on logout even when API logout fails', async () => {
    const { useAuthStore } = await import('./useAuth')
    apiLogout.mockRejectedValueOnce(new Error('network'))

    useAuthStore.setState({
      user: { id: 1, email: 'user@example.com', role: 'customer' },
      isAuthenticated: true,
    })

    await useAuthStore.getState().logout()

    expect(useAuthStore.getState().user).toBeNull()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })
})

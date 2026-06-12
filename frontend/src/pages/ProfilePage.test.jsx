import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProfilePage from './ProfilePage'

import { updateMe, uploadAvatar, deleteAvatar } from '@/api/auth'

const setUserMock = vi.fn()
let mockUser = {
  id: 1,
  email: 'admin@test.com',
  full_name: 'Admin User',
  role: 'admin',
  org_id: 1,
  org_name: 'OSD',
  phone: '',
  avatar_url: null,
  avatar_color: 'blue',
}

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ user: mockUser, setUser: setUserMock }),
}))

vi.mock('@/api/auth', () => ({
  updateMe: vi.fn(),
  uploadAvatar: vi.fn(),
  deleteAvatar: vi.fn(),
}))

const RouterWrapper = ({ children }) => (
  <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    {children}
  </MemoryRouter>
)

beforeEach(() => {
  setUserMock.mockClear()
  updateMe.mockReset()
  uploadAvatar.mockReset()
  deleteAvatar.mockReset()
  mockUser = {
    id: 1,
    email: 'admin@test.com',
    full_name: 'Admin User',
    role: 'admin',
    org_id: 1,
    org_name: 'OSD',
    phone: '',
    avatar_url: null,
    avatar_color: 'blue',
  }
})

describe('ProfilePage', () => {
  it('renders profile heading and avatar fallback initials', () => {
    render(<ProfilePage />, { wrapper: RouterWrapper })
    expect(screen.getByRole('heading', { level: 1, name: /My Profile/i })).toBeInTheDocument()
    // "Admin User" → AU
    expect(screen.getAllByText('AU').length).toBeGreaterThan(0)
  })

  it('save profile calls updateMe and refreshes the auth store', async () => {
    updateMe.mockResolvedValue({ ...mockUser, full_name: 'Renamed Admin', avatar_color: 'orange' })
    render(<ProfilePage />, { wrapper: RouterWrapper })

    const nameInput = screen.getByLabelText(/Full name/i)
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'Renamed Admin')

    // Pick "Orange" — one of the theme-aligned palette options.
    await userEvent.click(screen.getByRole('button', { name: /Orange/i }))
    await userEvent.click(screen.getByRole('button', { name: /Save profile/i }))

    await waitFor(() => expect(updateMe).toHaveBeenCalledTimes(1))
    expect(updateMe).toHaveBeenCalledWith(expect.objectContaining({
      full_name: 'Renamed Admin',
      avatar_color: 'orange',
    }))
    expect(setUserMock).toHaveBeenCalled()
  })

  it('rejects an invalid file type before calling uploadAvatar', async () => {
    render(<ProfilePage />, { wrapper: RouterWrapper })
    const input = screen.getByLabelText(/Upload avatar file/i)
    const badFile = new File(['fake'], 'evil.svg', { type: 'image/svg+xml' })
    // fireEvent bypasses userEvent's accept-attribute check so we exercise the
    // JS validation path directly.
    fireEvent.change(input, { target: { files: [badFile] } })

    await waitFor(() => expect(screen.getByText(/Unsupported file type/i)).toBeInTheDocument())
    expect(uploadAvatar).not.toHaveBeenCalled()
  })

  it('uploads a valid PNG by calling uploadAvatar', async () => {
    uploadAvatar.mockResolvedValue({ ...mockUser, avatar_url: '/api/auth/me/avatar/file?v=1' })
    render(<ProfilePage />, { wrapper: RouterWrapper })
    const input = screen.getByLabelText(/Upload avatar file/i)
    const file = new File(['\x89PNG\r\n\x1a\n'], 'me.png', { type: 'image/png' })
    await userEvent.upload(input, file)
    await waitFor(() => expect(uploadAvatar).toHaveBeenCalledTimes(1))
    expect(setUserMock).toHaveBeenCalledWith(expect.objectContaining({ avatar_url: expect.stringContaining('/api/auth/me/avatar/file') }))
  })

  it('shows a Remove button when avatar_url exists and calls deleteAvatar', async () => {
    mockUser = { ...mockUser, avatar_url: '/api/auth/me/avatar/file?v=42' }
    deleteAvatar.mockResolvedValue({ ...mockUser, avatar_url: null })
    render(<ProfilePage />, { wrapper: RouterWrapper })

    const removeBtn = screen.getByRole('button', { name: /Remove avatar/i })
    await userEvent.click(removeBtn)

    await waitFor(() => expect(deleteAvatar).toHaveBeenCalledTimes(1))
    expect(setUserMock).toHaveBeenCalled()
  })
})

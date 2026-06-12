import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Layout from './Layout'

import { getNotifications, markAllRead, markRead } from '@/api/notifications'

let mockUser = { id: 1, email: 'demo@example.com', full_name: 'Demo User', role: 'admin' }
const logoutMock = vi.fn()

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ user: mockUser, logout: logoutMock, isAuthenticated: true }),
}))

vi.mock('@/hooks/useRole', () => ({
  useRole: () => ({ role: mockUser.role, isAdmin: mockUser.role === 'admin', isStaff: mockUser.role === 'staff', isCustomer: mockUser.role === 'customer' }),
}))

vi.mock('@/hooks/useSocket', () => ({ useSocket: () => undefined }))

vi.mock('@/hooks/useNotificationStore', () => ({
  useNotificationStore: () => ({
    unreadCount: 0,
    setUnreadCount: vi.fn(),
    clearUnread: vi.fn(),
    toasts: [],
    addToast: vi.fn(),
    removeToast: vi.fn(),
  }),
}))

vi.mock('@/hooks/useCommandPalette', () => ({
  useCommandPalette: () => ({ open: false, setOpen: vi.fn() }),
}))

vi.mock('@/api/notifications', () => ({
  getNotifications: vi.fn(),
  markAllRead: vi.fn(),
  markRead: vi.fn(),
}))

vi.mock('@/components/ui/CommandPalette', () => ({
  default: () => null,
}))

vi.mock('./ProfileSettings', () => ({
  default: () => null,
}))

function renderLayout() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Layout><div data-testid="page-body">Body</div></Layout>
    </MemoryRouter>,
  )
}

describe('Layout sidebar', () => {
  beforeEach(() => {
    mockUser = { id: 1, email: 'demo@example.com', full_name: 'Demo User', role: 'admin' }
    getNotifications.mockResolvedValue([])
    markAllRead.mockResolvedValue(undefined)
    markRead.mockResolvedValue(undefined)
  })

  it('shows the WorkDesk brand and Client Support Platform subtitle', () => {
    renderLayout()
    expect(screen.getByText(/WorkDesk/i)).toBeInTheDocument()
    expect(screen.getByText(/Client Support Platform/i)).toBeInTheDocument()
  })

  it('renames Projects to SEO Projects in the sidebar', () => {
    renderLayout()
    const links = screen.getAllByRole('link', { name: /SEO Projects/i })
    expect(links.length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: /^Projects$/ })).not.toBeInTheDocument()
  })

  it('admin sidebar lists all expected sections including Client Management and Billing', () => {
    renderLayout()
    expect(screen.getAllByText('Client Management').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Delivery').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Support').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Billing').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Reporting').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /Organizations/ }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /SLA Policies/ }).length).toBeGreaterThan(0)
  })

  it('staff sidebar hides admin-only billing and shows Delivery + Reporting', () => {
    mockUser = { id: 2, email: 'staff@example.com', full_name: 'Staff One', role: 'staff' }
    renderLayout()
    expect(screen.getAllByText('Delivery').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Reporting').length).toBeGreaterThan(0)
    expect(screen.queryByText('Billing')).not.toBeInTheDocument()
    expect(screen.queryByText('Client Management')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Organizations/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /SLA Policies/ })).not.toBeInTheDocument()
  })

  it('customer sidebar shows My Services + My Tickets and hides admin areas', () => {
    mockUser = { id: 3, email: 'cust@example.com', full_name: 'Customer One', role: 'customer' }
    renderLayout()
    expect(screen.getAllByText('My Services').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /My Tickets/ }).length).toBeGreaterThan(0)
    expect(screen.queryByText('Client Management')).not.toBeInTheDocument()
    expect(screen.queryByText('Billing')).not.toBeInTheDocument()
    expect(screen.queryByText('Reporting')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Organizations/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^All Tickets$/ })).not.toBeInTheDocument()
  })
})

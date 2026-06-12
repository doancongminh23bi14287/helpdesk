import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DashboardPage from './DashboardPage'

import { listUsers } from '@/api/users'
import { listOrganizations } from '@/api/organizations'
import { getTickets } from '@/api/tickets'
import { listInvoices, listMyInvoices } from '@/api/invoices'
import { getMySubscriptions, listSubscriptions } from '@/api/subscriptions'
import { listProjects } from '@/api/projects'
import client from '@/api/client'

let mockUser = { id: 1, role: 'admin', org_id: 1 }

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ user: mockUser }),
}))

vi.mock('@/hooks/useTickets', () => ({
  useTickets: () => ({ tickets: [], loading: false }),
}))

vi.mock('@/hooks/useServices', () => ({
  useServices: () => ({ services: { hosting: [], subscriptions: [] }, loading: false }),
}))

vi.mock('@/api/users', () => ({ listUsers: vi.fn() }))
vi.mock('@/api/organizations', () => ({ listOrganizations: vi.fn() }))
vi.mock('@/api/tickets', () => ({ getTickets: vi.fn() }))
vi.mock('@/api/invoices', () => ({ listInvoices: vi.fn(), listMyInvoices: vi.fn() }))
vi.mock('@/api/subscriptions', () => ({ getMySubscriptions: vi.fn(), listSubscriptions: vi.fn() }))
vi.mock('@/api/projects', () => ({ listProjects: vi.fn() }))
vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}))

const wrap = (ui) => (
  <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{ui}</MemoryRouter>
)

beforeEach(() => {
  mockUser = { id: 1, role: 'admin', org_id: 1 }
  listUsers.mockResolvedValue({ total: 5 })
  listOrganizations.mockResolvedValue({ total: 3 })
  getTickets.mockResolvedValue({ total: 2 })
  listInvoices.mockResolvedValue({ items: [] })
  listMyInvoices.mockResolvedValue([])
  getMySubscriptions.mockResolvedValue([])
  listSubscriptions.mockResolvedValue([])
  listProjects.mockResolvedValue({ items: [] })
  client.get.mockResolvedValue({ data: { overdue_invoices: 0, sla_breached_tickets: 0, celery_workers: 'running' } })
})

describe('DashboardPage', () => {
  it('does not render the removed Recent Activity card', async () => {
    render(wrap(<DashboardPage />))
    await waitFor(() => expect(listOrganizations).toHaveBeenCalled())
    expect(screen.queryByText(/Recent Activity/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/No recent activity/i)).not.toBeInTheDocument()
  })

  it('renders 0 ₫ instead of NaN when invoice totals are missing', async () => {
    // listInvoices returns invoices whose total is undefined/null/string
    listInvoices.mockResolvedValue({
      items: [
        { status: 'sent', total: undefined },
        { status: 'overdue', total: null },
        { status: 'sent', total: 'not-a-number' },
      ],
    })

    render(wrap(<DashboardPage />))
    await waitFor(() => expect(listInvoices).toHaveBeenCalled())

    // The outstanding card must show "0 ₫" and no occurrence of "NaN".
    await waitFor(() => {
      const candidates = screen.queryAllByText((_, node) => node?.textContent?.includes('₫'))
      expect(candidates.length).toBeGreaterThan(0)
    })
    expect(document.body.textContent).not.toMatch(/NaN/)
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import NewTicketPage from './NewTicketPage'

import { listOrganizations, getOrgServices } from '@/api/organizations'
import { listUsers } from '@/api/users'

const submit = vi.fn()
const RouterWrapper = ({ children }) => (
  <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    {children}
  </MemoryRouter>
)

vi.mock('@/hooks/useTickets', () => ({
  useCreateTicket: () => ({ submit, loading: false, error: null }),
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ user: { id: 1, role: 'customer', org_id: 10 } }),
}))

vi.mock('@/hooks/useRole', () => ({
  useRole: () => ({ isCustomer: true, isStaff: false, isAdmin: false }),
}))

vi.mock('@/api/organizations', () => ({
  listOrganizations: vi.fn(),
  getOrgServices: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))

vi.mock('@/api/attachments', () => ({
  uploadAttachment: vi.fn(),
}))

beforeEach(() => {
  listOrganizations.mockResolvedValue([{ id: 10, name: 'Client Org' }])
  getOrgServices.mockResolvedValue([])
  listUsers.mockResolvedValue([])
})

describe('NewTicketPage', () => {
  it('validates required customer ticket fields', async () => {
    render(<NewTicketPage />, { wrapper: RouterWrapper })

    await userEvent.click(await screen.findByRole('button', { name: /submit ticket/i }))

    expect(await screen.findByText('Subject is required')).toBeInTheDocument()
    expect(screen.getByText('Please select a service')).toBeInTheDocument()
    expect(screen.getByText('Please select a ticket type')).toBeInTheDocument()
    expect(screen.getByText('Please describe your issue')).toBeInTheDocument()
    expect(submit).not.toHaveBeenCalled()
  })

  it('ticket type dropdown only offers backend-allowed values, not "support"', async () => {
    render(<NewTicketPage />, { wrapper: RouterWrapper })

    // Wait for orgs to load
    await screen.findByRole('button', { name: /submit ticket/i })

    const values = Array.from(document.querySelectorAll('option')).map((o) => o.value)
    // Allowed backend enum values are present
    expect(values).toEqual(expect.arrayContaining([
      'Bug', 'Incident', 'Question', 'Unspecified',
      'Service SaaS', 'Service Hosting', 'Renewal',
    ]))
    // Invalid values must NOT be offered
    expect(values).not.toContain('support')
    expect(values).not.toContain('Support')
  })
})

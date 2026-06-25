import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TicketDetailPage from './TicketDetailPage'

let mockUser = { id: 1, email: 'customer@example.com', role: 'customer' }
let mockRole = { isCustomer: true, isStaff: false, isAdmin: false }

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ user: mockUser }),
}))

vi.mock('@/hooks/useRole', () => ({
  useRole: () => mockRole,
}))

vi.mock('@/hooks/useTickets', () => ({
  useTicket: () => ({
    loading: false,
    ticket: {
      id: 10,
      subject: 'Cannot login',
      source: 'portal',
      status: 'Open',
      priority: 'Medium',
      description: 'Help',
    },
    comments: [
      { id: 1, author_email: 'staff@example.com', content: 'Public reply', is_internal: false },
      { id: 2, author_email: 'staff@example.com', content: 'Internal note', is_internal: true },
    ],
    activities: [],
    sla: null,
    reply: vi.fn(),
    refetch: vi.fn(),
  }),
}))

vi.mock('@/api/attachments', () => ({
  getAttachments: () => Promise.resolve([]),
  uploadAttachment: () => Promise.resolve({}),
}))

vi.mock('@/api/tickets', () => ({
  updateTicket: () => Promise.resolve({}),
  assignTicket: () => Promise.resolve({}),
  getTransferRequest: () => Promise.reject(new Error('none')),
  createTransferRequest: () => Promise.resolve({}),
  acceptTransfer: () => Promise.resolve({}),
  declineTransfer: () => Promise.resolve({}),
}))

vi.mock('@/api/users', () => ({
  listUsers: () => Promise.resolve([]),
}))

describe('TicketDetailPage', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(query => ({
        matches: false, media: query, onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(),
        addEventListener: vi.fn(), removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    mockUser = { id: 1, email: 'customer@example.com', role: 'customer' }
    mockRole = { isCustomer: true, isStaff: false, isAdmin: false }
  })

  it('hides internal notes for customer users defensively', () => {
    render(
      <MemoryRouter
        initialEntries={['/tickets/10']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/tickets/:id" element={<TicketDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Public reply')).toBeInTheDocument()
    expect(screen.queryByText('Internal note')).not.toBeInTheDocument()
  })

  it('shows an internal badge for staff users', () => {
    mockUser = { id: 2, email: 'staff@example.com', role: 'staff' }
    mockRole = { isCustomer: false, isStaff: true, isAdmin: false }

    render(
      <MemoryRouter
        initialEntries={['/tickets/10']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/tickets/:id" element={<TicketDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getAllByText('Internal note').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/^Internal$/i).length).toBeGreaterThan(0)
  })
})

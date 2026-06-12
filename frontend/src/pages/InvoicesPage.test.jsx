import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import InvoicesPage from './InvoicesPage'

const RouterWrapper = ({ children }) => (
  <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    {children}
  </MemoryRouter>
)

vi.mock('@/hooks/useAuth', () => ({
  useAuthStore: () => ({ user: { id: 1, role: 'customer' } }),
}))

vi.mock('@/api/invoices', () => ({
  listMyInvoices: vi.fn().mockResolvedValue([
    {
      id: 1,
      invoice_number: 'INV-001',
      org_name: 'Client Org',
      subscription_plan_name: 'Support Plan',
      status: 'sent',
      issue_date: '2026-06-01',
      due_date: '2026-06-15',
      subtotal: 100000,
      tax_rate: 10,
      tax_amount: 10000,
      total: 110000,
      lines: [
        {
          id: 1,
          description: 'Managed support',
          quantity: 1,
          unit_price: 100000,
          line_total: 100000,
        },
      ],
    },
  ]),
}))

describe('InvoicesPage', () => {
  it('renders invoice list and detail data', async () => {
    render(<InvoicesPage />, { wrapper: RouterWrapper })

    expect(await screen.findByText('INV-001')).toBeInTheDocument()
    fireEvent.click(screen.getByText('INV-001'))

    await waitFor(() => {
      expect(screen.getByText('Managed support')).toBeInTheDocument()
    })
    expect(screen.getAllByText('Support Plan').length).toBeGreaterThan(0)
  })
})

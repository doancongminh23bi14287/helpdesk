import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import AdminInvoicesPage from './InvoicesPage'

const addInvoicePayment = vi.fn().mockResolvedValue({})
const listInvoicePayments = vi.fn().mockResolvedValue([])
const getInvoice = vi.fn().mockResolvedValue({
  id: 1,
  invoice_number: 'INV-100',
  org_name: 'Client Org',
  subscription_plan_name: 'Support',
  status: 'sent',
  issue_date: '2026-06-01',
  due_date: '2026-06-15',
  subtotal: 100000,
  tax_rate: 10,
  tax_amount: 10000,
  total: 110000,
  lines: [],
})

vi.mock('@/api/invoices', () => ({
  listInvoices: vi.fn().mockResolvedValue({
    items: [{
      id: 1,
      invoice_number: 'INV-100',
      org_name: 'Client Org',
      subscription_plan_name: 'Support',
      status: 'sent',
      issue_date: '2026-06-01',
      due_date: '2026-06-15',
      subtotal: 100000,
      tax_rate: 10,
      tax_amount: 10000,
      total: 110000,
      lines: [],
    }],
    total: 1,
    pages: 1,
  }),
  getInvoice: (...args) => getInvoice(...args),
  sendInvoice: vi.fn(),
  markInvoicePaid: vi.fn(),
  cancelInvoice: vi.fn(),
  deleteInvoice: vi.fn(),
  generateFromSubscriptions: vi.fn(),
  listInvoicePayments: (...args) => listInvoicePayments(...args),
  addInvoicePayment: (...args) => addInvoicePayment(...args),
  downloadInvoicePdf: vi.fn(),
}))

describe('AdminInvoicesPage payments', () => {
  it('renders and submits the add payment form', async () => {
    render(<AdminInvoicesPage />)

    fireEvent.click(await screen.findByText('INV-100'))
    expect(await screen.findByText('Payment History')).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText('Amount'), '50000')
    await userEvent.type(screen.getByPlaceholderText('Reference'), 'BANK-1')
    await userEvent.type(screen.getByPlaceholderText('Note'), 'Partial payment')
    await userEvent.click(screen.getByRole('button', { name: /add payment/i }))

    await waitFor(() => {
      expect(addInvoicePayment).toHaveBeenCalledWith(1, {
        amount: '50000',
        method: 'bank_transfer',
        reference: 'BANK-1',
        note: 'Partial payment',
      })
    })
  })
})

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { DocumentTextIcon } from '@heroicons/react/24/outline'
import { Modal } from '@/components/ui/Modal'
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  MobileCardList,
  MobileDataCard,
  MobileDataRow,
  ResponsiveTableViewport,
  Spinner,
} from '@/components/ui'
import { listMyInvoices, downloadInvoicePdf } from '@/api/invoices'
import { useAuthStore } from '@/hooks/useAuth'
import { formatCurrencyVND as fmtVND, formatDate as fmtDate } from '@/lib/utils'
import { STATUS_COLORS } from '@/lib/statusColors'

function StatusBadge({ status }) {
  const cls = STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-500'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${cls} ${status === 'cancelled' ? 'line-through' : ''}`}>
      {status ?? '—'}
    </span>
  )
}

function InvoiceDetailModal({ invoice, onClose }) {
  if (!invoice) return null
  return (
    <Modal open={!!invoice} onClose={onClose} title={`Invoice ${invoice.invoice_number}`}>
      <div className="space-y-5">
        {/* Header info */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Organisation</p>
            <p className="font-medium text-foreground mt-0.5">{invoice.org_name ?? invoice.org_id}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Plan</p>
            <p className="font-medium text-foreground mt-0.5">{invoice.subscription_plan_name ?? '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Issue Date</p>
            <p className="font-medium text-foreground mt-0.5">{fmtDate(invoice.issue_date)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Due Date</p>
            <p className="font-medium text-foreground mt-0.5">{fmtDate(invoice.due_date)}</p>
          </div>
          {invoice.paid_at && (
            <div>
              <p className="text-xs text-muted-foreground">Paid At</p>
              <p className="font-medium text-foreground mt-0.5">{fmtDate(invoice.paid_at)}</p>
            </div>
          )}
          <div>
            <p className="text-xs text-muted-foreground">Status</p>
            <div className="mt-0.5"><StatusBadge status={invoice.status} /></div>
          </div>
        </div>

        {invoice.notes && (
          <div className="px-3 py-2 bg-muted/40 rounded-lg text-sm text-foreground">
            <p className="text-xs text-muted-foreground mb-1">Notes</p>
            {invoice.notes}
          </div>
        )}

        {/* Lines table */}
        {invoice.lines && invoice.lines.length > 0 && (
          <div className="border border-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Description</th>
                  <th className="text-right px-3 py-2 font-medium text-muted-foreground">Qty</th>
                  <th className="text-right px-3 py-2 font-medium text-muted-foreground">Unit Price</th>
                  <th className="text-right px-3 py-2 font-medium text-muted-foreground">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {invoice.lines.map((line) => (
                  <tr key={line.id}>
                    <td className="px-3 py-2 text-foreground">{line.description}</td>
                    <td className="px-3 py-2 text-right text-muted-foreground tabular-nums">{line.quantity}</td>
                    <td className="px-3 py-2 text-right text-muted-foreground tabular-nums">{fmtVND(line.unit_price)}</td>
                    <td className="px-3 py-2 text-right text-foreground tabular-nums">{fmtVND(line.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        )}

        {/* Totals */}
        <div className="border border-border rounded-lg p-4 space-y-2 text-sm">
          <div className="flex justify-between text-muted-foreground">
            <span>Subtotal</span>
            <span className="tabular-nums">{fmtVND(invoice.subtotal)}</span>
          </div>
          <div className="flex justify-between text-muted-foreground">
            <span>Tax ({Number(invoice.tax_rate ?? 0).toFixed(0)}%)</span>
            <span className="tabular-nums">{fmtVND(invoice.tax_amount)}</span>
          </div>
          <div className="flex justify-between font-bold text-foreground border-t border-border pt-2 mt-1">
            <span>Total</span>
            <span className="tabular-nums">{fmtVND(invoice.total)}</span>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => downloadInvoicePdf(invoice)}
            className="px-3 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
          >
            Download PDF
          </button>
        </div>
      </div>
    </Modal>
  )
}

export default function InvoicesPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    listMyInvoices()
      .then((data) => setInvoices(Array.isArray(data) ? data : []))
      .catch((err) => setError(err.message || 'Failed to load invoices'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (user?.role === 'admin' || user?.role === 'staff') {
      navigate('/admin/invoices', { replace: true })
      return
    }
    load()
  }, [])

  return (
    <div className="px-4 py-5 sm:p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-foreground">Invoices</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Your organisation's invoices</p>
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {loading ? (
          <LoadingState rows={4} className="px-4" label="Loading invoices" />
        ) : error ? (
          <ErrorState title="Could not load invoices" description={error} onRetry={load} className="m-4" />
        ) : invoices.length === 0 ? (
          <EmptyState
            icon={DocumentTextIcon}
            title="No invoices found"
            description="Your invoices will appear here once generated."
          />
        ) : (
          <ResponsiveTableViewport
            mobile={(
              <MobileCardList ariaLabel="Invoices">
                {invoices.map((inv) => (
                  <MobileDataCard
                    key={inv.id}
                    onClick={() => setSelected(inv)}
                    ariaLabel={`View invoice ${inv.invoice_number}`}
                    actions={(
                      <Button type="button" size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); setSelected(inv) }}>
                        View details
                      </Button>
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs text-muted-foreground">Invoice</p>
                        <h3 className="font-mono text-base font-semibold text-foreground">{inv.invoice_number}</h3>
                      </div>
                      <StatusBadge status={inv.status} />
                    </div>
                    <dl className="mt-3 divide-y divide-border">
                      <MobileDataRow label="Plan">{inv.subscription_plan_name || 'Not specified'}</MobileDataRow>
                      <MobileDataRow label="Issue date">{fmtDate(inv.issue_date)}</MobileDataRow>
                      <MobileDataRow label="Due date">{fmtDate(inv.due_date)}</MobileDataRow>
                      <MobileDataRow label="Total">{fmtVND(inv.total)}</MobileDataRow>
                    </dl>
                  </MobileDataCard>
                ))}
              </MobileCardList>
            )}
          >
          <table className="w-full min-w-[700px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Invoice #</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Plan</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Issue Date</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Due Date</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Total</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {invoices.map((inv) => (
                <tr
                  key={inv.id}
                  onClick={() => setSelected(inv)}
                  className="hover:bg-muted/30 transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3 font-mono text-foreground">{inv.invoice_number}</td>
                  <td className="px-4 py-3 text-foreground">{inv.subscription_plan_name ?? '—'}</td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{fmtDate(inv.issue_date)}</td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{fmtDate(inv.due_date)}</td>
                  <td className="px-4 py-3 text-foreground tabular-nums">{fmtVND(inv.total)}</td>
                  <td className="px-4 py-3"><StatusBadge status={inv.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          </ResponsiveTableViewport>
        )}
      </div>

      <InvoiceDetailModal invoice={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

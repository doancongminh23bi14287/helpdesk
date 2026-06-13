import { useState, useEffect, useCallback, useMemo } from 'react'
import { DocumentTextIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import {
  listInvoices, getInvoice, sendInvoice, markInvoicePaid, cancelInvoice, deleteInvoice,
  generateFromSubscriptions, listInvoicePayments, addInvoicePayment, downloadInvoicePdf,
} from '@/api/invoices'
import { formatCurrencyVND as fmtVND, formatDate as fmtDate } from '@/lib/utils'

const PER_PAGE = 20

const STATUS_COLORS = {
  draft:     'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
  sent:      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  paid:      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  overdue:   'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  cancelled: 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500',
}

function StatusBadge({ status }) {
  const cls = STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-500'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${cls} ${status === 'cancelled' ? 'line-through' : ''}`}>
      {status ?? '—'}
    </span>
  )
}

function PaymentSection({ invoice, onChanged }) {
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ amount: '', method: 'bank_transfer', reference: '', note: '' })

  const loadPayments = useCallback(async () => {
    if (!invoice?.id) return
    setLoading(true)
    setError('')
    try {
      setPayments(await listInvoicePayments(invoice.id))
    } catch (err) {
      setError(err?.message ?? 'Failed to load payments')
    } finally {
      setLoading(false)
    }
  }, [invoice?.id])

  useEffect(() => { loadPayments() }, [loadPayments])

  const paidTotal = payments.reduce((sum, p) => sum + Number(p.amount ?? 0), 0)
  const remaining = Math.max(0, Number(invoice?.total ?? 0) - paidTotal)

  const submit = async (e) => {
    e.preventDefault()
    if (!form.amount || Number(form.amount) <= 0) return
    setSaving(true)
    setError('')
    try {
      await addInvoicePayment(invoice.id, {
        amount: form.amount,
        method: form.method,
        reference: form.reference || null,
        note: form.note || null,
      })
      setForm({ amount: '', method: 'bank_transfer', reference: '', note: '' })
      await loadPayments()
      await onChanged?.()
    } catch (err) {
      setError(err?.message ?? 'Failed to add payment')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border border-border rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-sm text-foreground">Payment History</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Paid {fmtVND(paidTotal)} · Remaining {fmtVND(remaining)}
          </p>
        </div>
        {remaining > 0 && payments.length > 0 && invoice.status !== 'paid' && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
            Partial
          </span>
        )}
      </div>

      {error && <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1">{error}</div>}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner className="w-4 h-4" /> Loading payments</div>
      ) : payments.length === 0 ? (
        <p className="text-sm text-muted-foreground">No payments recorded yet.</p>
      ) : (
        <div className="divide-y divide-border text-sm">
          {payments.map((p) => (
            <div key={p.id} className="py-2 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium text-foreground">{p.method}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {p.reference || 'No reference'} · {fmtDate(p.paid_at)}
                </p>
                {p.note && <p className="text-xs text-muted-foreground mt-1">{p.note}</p>}
              </div>
              <span className="font-semibold tabular-nums text-foreground">{fmtVND(p.amount)}</span>
            </div>
          ))}
        </div>
      )}

      {invoice.status !== 'paid' && invoice.status !== 'cancelled' && (
        <form onSubmit={submit} className="grid grid-cols-2 gap-3 pt-2 border-t border-border">
          <input
            value={form.amount}
            onChange={(e) => setForm(f => ({ ...f, amount: e.target.value }))}
            type="number"
            min="1"
            step="0.01"
            placeholder="Amount"
            className="px-3 py-2 border border-input rounded-lg bg-background text-sm"
          />
          <select
            value={form.method}
            onChange={(e) => setForm(f => ({ ...f, method: e.target.value }))}
            className="px-3 py-2 border border-input rounded-lg bg-background text-sm"
          >
            <option value="bank_transfer">Bank transfer</option>
            <option value="cash">Cash</option>
            <option value="vnpay">VNPay</option>
            <option value="manual">Manual</option>
            <option value="other">Other</option>
          </select>
          <input
            value={form.reference}
            onChange={(e) => setForm(f => ({ ...f, reference: e.target.value }))}
            placeholder="Reference"
            className="px-3 py-2 border border-input rounded-lg bg-background text-sm"
          />
          <input
            value={form.note}
            onChange={(e) => setForm(f => ({ ...f, note: e.target.value }))}
            placeholder="Note"
            className="px-3 py-2 border border-input rounded-lg bg-background text-sm"
          />
          <button
            type="submit"
            disabled={saving || !form.amount}
            className="col-span-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {saving && <Spinner className="w-3.5 h-3.5" />}
            Add Payment
          </button>
        </form>
      )}
    </div>
  )
}

function InvoiceDetailModal({ invoice, onClose, onInvoiceChanged }) {
  if (!invoice) return null
  return (
    <Modal open={!!invoice} onClose={onClose} title={`Invoice ${invoice.invoice_number}`}>
      <div className="space-y-5">
        {/* Header info */}
        <div className="grid grid-cols-2 gap-3 text-sm">
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

        <PaymentSection invoice={invoice} onChanged={onInvoiceChanged} />
      </div>
    </Modal>
  )
}

export default function AdminInvoicesPage() {
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionMsg, setActionMsg] = useState('')
  const [selected, setSelected] = useState(null)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [actionLoading, setActionLoading] = useState(null) // invoice id being actioned
  const [filterStatus, setFilterStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)

  // Reset page when filter changes
  useEffect(() => { setPage(1) }, [filterStatus])

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError('')
      const params = { page, per_page: PER_PAGE }
      if (filterStatus !== 'all') params.status = filterStatus
      const data = await listInvoices(params)
      const allInvoices = Array.isArray(data?.items) ? data.items : []
      setInvoices(allInvoices)
      setTotal(data?.total ?? 0)
      setPages(data?.pages ?? 1)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to load invoices')
    } finally {
      setLoading(false)
    }
  }, [filterStatus, page])

  useEffect(() => { load() }, [load])

  // Summary computations from current page invoices
  const summary = useMemo(() => {
    const now = new Date()
    const currentMonth = now.getMonth()
    const currentYear = now.getFullYear()
    let outstanding = 0
    let paidThisMonth = 0
    for (const inv of invoices) {
      if (inv.status === 'sent' || inv.status === 'overdue') {
        outstanding += inv.total ?? 0
      }
      if (inv.status === 'paid' && inv.paid_at) {
        const paidDate = new Date(inv.paid_at)
        if (paidDate.getMonth() === currentMonth && paidDate.getFullYear() === currentYear) {
          paidThisMonth += inv.total ?? 0
        }
      }
    }
    return { outstanding, paidThisMonth }
  }, [invoices])

  const handleSend = async (inv) => {
    setActionLoading(inv.id)
    setError('')
    try {
      await sendInvoice(inv.id)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to send invoice')
    } finally {
      setActionLoading(null)
    }
  }

  const handleMarkPaid = async (inv) => {
    setActionLoading(inv.id)
    setError('')
    try {
      await markInvoicePaid(inv.id)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to mark invoice as paid')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancel = async () => {
    if (!cancelTarget) return
    setCancelling(true)
    setError('')
    try {
      await cancelInvoice(cancelTarget.id)
      setCancelTarget(null)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to cancel invoice')
      setCancelTarget(null)
    } finally {
      setCancelling(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    setError('')
    try {
      await deleteInvoice(deleteTarget.id)
      setDeleteTarget(null)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to delete invoice')
      setDeleteTarget(null)
    } finally {
      setDeleting(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setError('')
    setActionMsg('')
    try {
      const result = await generateFromSubscriptions()
      const count = result?.generated ?? result?.count ?? (Array.isArray(result) ? result.length : 0)
      setActionMsg(`Generated ${count} invoice${count !== 1 ? 's' : ''} from subscriptions.`)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to generate invoices')
    } finally {
      setGenerating(false)
    }
  }

  const handleRowClick = (e, inv) => {
    // Don't open detail if clicking action buttons
    if (e.target.closest('button')) return
    setSelected(inv)
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Invoices</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage all customer invoices</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {generating && <Spinner className="w-3.5 h-3.5" />}
          Generate from Subscriptions
        </button>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}

      {actionMsg && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700 dark:bg-emerald-900/20 dark:border-emerald-800 dark:text-emerald-400">
          {actionMsg}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
          <option value="cancelled">Cancelled</option>
        </select>
        {filterStatus !== 'all' && (
          <button
            onClick={() => setFilterStatus('all')}
            className="px-3 py-2 border border-input rounded-lg bg-background text-muted-foreground text-sm hover:text-foreground hover:bg-muted transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} className="border-t-0 border-b border-border" />
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Invoice #</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Org</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Plan</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Issue Date</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Due Date</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Total</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          {loading ? (
            <tbody>
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-border">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 bg-muted rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : invoices.length === 0 ? (
            <tbody>
              <tr>
                <td colSpan={8}>
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <DocumentTextIcon className="w-10 h-10 text-muted-foreground mb-3" />
                    <p className="font-medium text-foreground">No invoices yet</p>
                    <p className="text-sm text-muted-foreground mt-1">Generate invoices from subscriptions to get started</p>
                  </div>
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody className="divide-y divide-border">
              {invoices.map((inv) => {
                const isActioning = actionLoading === inv.id
                return (
                  <tr
                    key={inv.id}
                    onClick={(e) => handleRowClick(e, inv)}
                    className={`hover:bg-muted/30 transition-colors cursor-pointer ${inv.status === 'overdue' ? 'bg-red-50 dark:bg-red-900/10' : ''}`}
                  >
                    <td className="px-4 py-3 font-mono text-foreground">{inv.invoice_number}</td>
                    <td className="px-4 py-3 text-foreground">{inv.org_name ?? inv.org_id}</td>
                    <td className="px-4 py-3 text-foreground">{inv.subscription_plan_name ?? '—'}</td>
                    <td className="px-4 py-3"><StatusBadge status={inv.status} /></td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">{fmtDate(inv.issue_date)}</td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">{fmtDate(inv.due_date)}</td>
                    <td className={`px-4 py-3 tabular-nums ${inv.status === 'paid' ? 'text-emerald-600 dark:text-emerald-400 font-medium' : 'text-foreground'}`}>{fmtVND(inv.total)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        {(inv.status === 'draft' || inv.status === 'sent') && (
                          <button
                            onClick={() => handleSend(inv)}
                            disabled={isActioning}
                            title={inv.status === 'sent' ? 'Resend invoice email' : 'Send invoice'}
                            className="px-2.5 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/40 transition-colors disabled:opacity-50 flex items-center gap-1"
                          >
                            {isActioning ? <Spinner className="w-3 h-3" /> : null}
                            {inv.status === 'sent' ? 'Resend' : 'Send'}
                          </button>
                        )}
                        {(inv.status === 'sent' || inv.status === 'overdue') && (
                          <button
                            onClick={() => handleMarkPaid(inv)}
                            disabled={isActioning}
                            title="Mark as paid"
                            className="px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-400 dark:hover:bg-emerald-900/40 transition-colors disabled:opacity-50 flex items-center gap-1"
                          >
                            {isActioning ? <Spinner className="w-3 h-3" /> : null}
                            Mark Paid
                          </button>
                        )}
                        {(inv.status === 'draft' || inv.status === 'sent') && (
                          <button
                            onClick={() => setCancelTarget(inv)}
                            disabled={isActioning}
                            title="Cancel invoice"
                            className="px-2.5 py-1 rounded-md text-xs font-medium bg-red-50 text-red-700 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50"
                          >
                            Cancel
                          </button>
                        )}
                        {inv.status === 'cancelled' && (
                          <button
                            onClick={() => setDeleteTarget(inv)}
                            disabled={isActioning}
                            title="Delete invoice"
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                          >
                            <TrashIcon className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          )}
        </table>
        </div>
        {/* Summary row */}
        {!loading && invoices.length > 0 && (
          <div className="border-t border-border px-4 py-3 flex items-center gap-6 text-sm bg-muted/20">
            <span className="text-muted-foreground">
              Outstanding (sent + overdue):
              <span className="ml-1.5 font-semibold text-foreground tabular-nums">{fmtVND(summary.outstanding)}</span>
              <span className="ml-1 text-xs text-muted-foreground">(this page)</span>
            </span>
            <span className="text-muted-foreground">
              Paid this month:
              <span className="ml-1.5 font-semibold text-emerald-600 dark:text-emerald-400 tabular-nums">{fmtVND(summary.paidThisMonth)}</span>
              <span className="ml-1 text-xs text-muted-foreground">(this page)</span>
            </span>
          </div>
        )}
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
      </div>

      {/* Detail Modal */}
      <InvoiceDetailModal
        invoice={selected}
        onClose={() => setSelected(null)}
        onInvoiceChanged={async () => {
          if (!selected) return
          const fresh = await getInvoice(selected.id)
          setSelected(fresh)
          await load()
        }}
      />

      {/* Delete Confirmation Modal */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Invoice">
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Permanently delete invoice{' '}
            <span className="font-semibold">{deleteTarget?.invoice_number}</span>
            {deleteTarget?.org_name ? ` for ${deleteTarget.org_name}` : ''}?
            This cannot be undone.
          </p>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => setDeleteTarget(null)}
              className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Keep
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {deleting && <Spinner className="w-3.5 h-3.5" />}
              Delete
            </button>
          </div>
        </div>
      </Modal>

      {/* Cancel Confirmation Modal */}
      <Modal open={!!cancelTarget} onClose={() => setCancelTarget(null)} title="Cancel Invoice">
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Are you sure you want to cancel invoice{' '}
            <span className="font-semibold">{cancelTarget?.invoice_number}</span>
            {cancelTarget?.org_name ? ` for ${cancelTarget.org_name}` : ''}?
            This action cannot be undone.
          </p>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => setCancelTarget(null)}
              className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Keep Invoice
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {cancelling && <Spinner className="w-3.5 h-3.5" />}
              Cancel Invoice
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

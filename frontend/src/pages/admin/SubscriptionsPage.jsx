import { useState, useEffect } from 'react'
import { PlusIcon, XMarkIcon, CreditCardIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import {
  listSubscriptions, createSubscription, cancelSubscription, deleteSubscription,
} from '@/api/subscriptions'
import { listOrganizations } from '@/api/organizations'
import { listItems } from '@/api/items'
import { formatCurrencyVND as fmtVND, formatDate as fmtDate } from '@/lib/utils'

const PER_PAGE = 20

const ROW_BG = {
  past_due:  'bg-amber-50 dark:bg-amber-900/10',
  expired:   'bg-red-50 dark:bg-red-900/10',
  trial:     'bg-purple-50 dark:bg-purple-900/10',
  cancelled: 'opacity-60',
}

const STATUS_COLORS = {
  trial:     'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  active:    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  past_due:  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  cancelled: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
  expired:   'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}

function computePeriodEnd(startStr, billingCycle) {
  if (!startStr || !billingCycle) return null
  const d = new Date(startStr)
  if (billingCycle === 'monthly') d.setMonth(d.getMonth() + 1)
  else if (billingCycle === 'quarterly') d.setMonth(d.getMonth() + 3)
  else if (billingCycle === 'yearly') d.setFullYear(d.getFullYear() + 1)
  else return null
  return d
}

const EMPTY_FORM = {
  org_id: '', plan_id: '', start_date: '',
  billing_cycle: 'monthly', due_days: '15', tax_rate: '0', end_date: '',
}

const SELECT_CLS = 'w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring'

const CYCLE_LABELS = { monthly: 'Monthly', quarterly: 'Quarterly', yearly: 'Annual' }

function cyclePriceFor(basePrice, cycle) {
  if (basePrice == null) return null
  if (cycle === 'quarterly') return Math.round(basePrice * 3 * 0.95)
  if (cycle === 'yearly')    return Math.round(basePrice * 12 * 0.8)
  return Math.round(basePrice)
}

function SubscriptionForm({ items, orgs, onSubmit, onCancel, loading }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const selectedItem = items.find((i) => String(i.id) === String(form.plan_id))
  const basePrice = selectedItem?.unit_price != null ? Number(selectedItem.unit_price) : null
  const taxRate = Number(form.tax_rate) || 0

  const cyclePrice = cyclePriceFor(basePrice, form.billing_cycle)
  const taxAmount = cyclePrice != null ? Math.round(cyclePrice * taxRate / 100) : null
  const totalPrice = cyclePrice != null ? cyclePrice + (taxAmount ?? 0) : null

  const periodEnd = computePeriodEnd(form.start_date, form.billing_cycle)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.org_id) { setError('Organisation is required'); return }
    if (!form.plan_id) { setError('Plan is required'); return }
    if (!form.start_date) { setError('Start date is required'); return }
    try {
      const payload = {
        org_id: Number(form.org_id),
        plan_id: Number(form.plan_id),
        start_date: form.start_date,
        billing_cycle: form.billing_cycle,
        due_days: Number(form.due_days) || 15,
        tax_rate: Number(form.tax_rate) || 0,
      }
      if (form.end_date) payload.end_date = form.end_date
      await onSubmit(payload)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'An error occurred')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Organisation <span className="text-red-500">*</span>
        </label>
        <select value={form.org_id} onChange={set('org_id')} className={SELECT_CLS}>
          <option value="">Select an organisation…</option>
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>{o.name} ({o.code})</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Plan (Service) <span className="text-red-500">*</span>
        </label>
        <select value={form.plan_id} onChange={set('plan_id')} className={SELECT_CLS}>
          <option value="">Select a service…</option>
          {items.map((i) => (
            <option key={i.id} value={i.id}>
              {i.code} ({i.unit}) — {fmtVND(i.unit_price)}/month
            </option>
          ))}
        </select>
      </div>

      {/* Billing Cycle */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Billing Cycle</label>
        <div className="flex rounded-lg border border-input overflow-hidden">
          {['monthly', 'quarterly', 'yearly'].map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setForm((f) => ({ ...f, billing_cycle: c }))}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                form.billing_cycle === c
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-foreground hover:bg-muted'
              }`}
            >
              {CYCLE_LABELS[c]}
            </button>
          ))}
        </div>
        {basePrice != null && (
          <div className="mt-2 flex gap-1 text-xs text-muted-foreground">
            {['monthly', 'quarterly', 'yearly'].map((c) => {
              const p = cyclePriceFor(basePrice, c)
              return (
                <span
                  key={c}
                  className={`flex-1 text-center px-1 py-0.5 rounded ${form.billing_cycle === c ? 'bg-primary/10 text-primary font-medium' : ''}`}
                >
                  {fmtVND(p)}
                </span>
              )
            })}
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Start Date <span className="text-red-500">*</span>
        </label>
        <input
          type="date"
          value={form.start_date}
          onChange={set('start_date')}
          className={SELECT_CLS}
        />
        {periodEnd && (
          <p className="mt-1.5 text-xs text-muted-foreground">
            Period ends: <span className="font-medium text-foreground">{fmtDate(periodEnd)}</span>
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Tax Rate (%)
          </label>
          <input
            type="number"
            min="0"
            max="100"
            step="0.01"
            value={form.tax_rate}
            onChange={set('tax_rate')}
            className={SELECT_CLS}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Payment due (days after invoice)
          </label>
          <input
            type="number"
            min="1"
            max="365"
            value={form.due_days}
            onChange={set('due_days')}
            className={SELECT_CLS}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          End Date <span className="text-muted-foreground text-xs">(optional)</span>
        </label>
        <input
          type="date"
          value={form.end_date}
          onChange={set('end_date')}
          className={SELECT_CLS}
        />
      </div>

      {/* Price summary */}
      {cyclePrice != null && (
        <div className="rounded-lg bg-muted/50 border border-border p-3 space-y-1.5 text-sm">
          <div className="flex justify-between text-muted-foreground">
            <span>Unit Price ({CYCLE_LABELS[form.billing_cycle]})</span>
            <span className="font-medium text-foreground">{fmtVND(cyclePrice)}</span>
          </div>
          <div className="flex justify-between text-muted-foreground">
            <span>Tax ({taxRate}%)</span>
            <span>{fmtVND(taxAmount ?? 0)}</span>
          </div>
          <div className="flex justify-between font-semibold text-foreground border-t border-border pt-1.5 mt-1">
            <span>Total per period</span>
            <span>{fmtVND(totalPrice)}</span>
          </div>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading}
          className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading && <Spinner className="w-3.5 h-3.5" />}
          Create Subscription
        </button>
      </div>
    </form>
  )
}

export default function SubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState([])
  const [items, setItems] = useState([])
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)

  // Reset page when filter changes
  useEffect(() => { setPage(1) }, [filterStatus])

  const load = async () => {
    try {
      setLoading(true)
      setError('')
      const params = { page, per_page: PER_PAGE }
      if (filterStatus !== 'all') params.status = filterStatus
      const [subsData, itemsData, orgsData] = await Promise.all([
        listSubscriptions(params),
        listItems(),
        listOrganizations({ per_page: 200 }),
      ])
      const allSubs = Array.isArray(subsData?.items) ? subsData.items : []
      setSubscriptions(allSubs)
      setTotal(subsData?.total ?? 0)
      setPages(subsData?.pages ?? 1)
      setItems(Array.isArray(itemsData) ? itemsData : (itemsData?.items ?? []))
      setOrgs(Array.isArray(orgsData) ? orgsData : (orgsData?.items ?? []))
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to load subscriptions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filterStatus, page])

  const handleCreate = async (form) => {
    setSaving(true)
    try {
      await createSubscription(form)
      setCreateOpen(false)
      load()
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteSubscription(deleteTarget.id)
      setDeleteTarget(null)
      load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to delete subscription')
      setDeleteTarget(null)
    } finally {
      setDeleting(false)
    }
  }

  const handleCancel = async () => {
    if (!cancelTarget) return
    setCancelling(true)
    try {
      await cancelSubscription(cancelTarget.id)
      setCancelTarget(null)
      load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to cancel subscription')
      setCancelTarget(null)
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Subscriptions</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage all customer subscriptions</p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <PlusIcon className="w-4 h-4" />
          Create Subscription
        </button>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
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
          <option value="trial">Trial</option>
          <option value="active">Active</option>
          <option value="past_due">Past Due</option>
          <option value="cancelled">Cancelled</option>
          <option value="expired">Expired</option>
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
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Org</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Plan</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Start Date</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Next Billing</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Unit Price</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          {loading ? (
            <tbody>
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-border">
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 bg-muted rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : subscriptions.length === 0 ? (
            <tbody>
              <tr>
                <td colSpan={7}>
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <CreditCardIcon className="w-10 h-10 text-muted-foreground mb-3" />
                    <p className="font-medium text-foreground">No subscriptions yet</p>
                    <p className="text-sm text-muted-foreground mt-1">Create one to get started</p>
                  </div>
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody className="divide-y divide-border">
              {subscriptions.map((sub) => (
                <tr key={sub.id} className={`hover:bg-muted/30 transition-colors ${ROW_BG[sub.status] ?? ''}`}>
                  <td className="px-4 py-3 font-medium text-foreground">{sub.org_name ?? sub.org_id}</td>
                  <td className="px-4 py-3 text-foreground">{sub.plan_name ?? sub.plan_id}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_COLORS[sub.status] ?? 'bg-muted text-muted-foreground'}`}>
                      {sub.status?.replace('_', ' ') ?? '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{fmtDate(sub.start_date)}</td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{fmtDate(sub.next_billing_date)}</td>
                  <td className="px-4 py-3 text-foreground tabular-nums">{sub.unit_price != null ? fmtVND(sub.unit_price) : '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {sub.status !== 'cancelled' && sub.status !== 'expired' && (
                        <button
                          onClick={() => setCancelTarget(sub)}
                          title="Cancel subscription"
                          className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        >
                          <XMarkIcon className="w-4 h-4" />
                        </button>
                      )}
                      {sub.status === 'cancelled' && (
                        <button
                          onClick={() => setDeleteTarget(sub)}
                          title="Delete subscription"
                          className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
        </div>
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
      </div>

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Subscription">
        <SubscriptionForm
          items={items}
          orgs={orgs}
          onSubmit={handleCreate}
          onCancel={() => setCreateOpen(false)}
          loading={saving}
        />
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Subscription">
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Permanently delete the subscription for{' '}
            <span className="font-semibold">{deleteTarget?.org_name ?? deleteTarget?.org_id}</span>
            {deleteTarget?.plan_name ? ` (${deleteTarget.plan_name})` : ''}?
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
      <Modal open={!!cancelTarget} onClose={() => setCancelTarget(null)} title="Cancel Subscription">
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Are you sure you want to cancel the subscription for{' '}
            <span className="font-semibold">{cancelTarget?.org_name ?? cancelTarget?.org_id}</span>
            {cancelTarget?.plan_name ? ` (${cancelTarget.plan_name})` : ''}?
            This action cannot be undone.
          </p>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => setCancelTarget(null)}
              className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Keep Subscription
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {cancelling && <Spinner className="w-3.5 h-3.5" />}
              Cancel Subscription
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import {
  PlusIcon,
  CreditCardIcon,
  EllipsisVerticalIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import {
  listSubscriptions,
  createSubscription,
  cancelSubscription,
  deleteSubscriptionPermanent,
} from '@/api/subscriptions'
import { listOrganizations } from '@/api/organizations'
import { listItems } from '@/api/items'
import { listServices } from '@/api/services'
import { formatCurrencyVND as fmtVND, formatDate as fmtDate } from '@/lib/utils'
import { PAGE_SIZE } from '@/lib/constants'
import { StatusBadge } from '@/components/StatusBadge'
import { TypeBadge } from '@/components/TypeBadge'
import { useNotificationStore } from '@/hooks/useNotificationStore'

const PER_PAGE = PAGE_SIZE

const CYCLE_LABELS = { monthly: 'Monthly', quarterly: 'Quarterly', yearly: 'Annual' }

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

function cyclePriceFor(basePrice, cycle) {
  if (basePrice == null) return null
  if (cycle === 'quarterly') return Math.round(basePrice * 3 * 0.95)
  if (cycle === 'yearly')    return Math.round(basePrice * 12 * 0.8)
  return Math.round(basePrice)
}

// ── Create Form ──────────────────────────────────────────────────────────────

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
        <input type="date" value={form.start_date} onChange={set('start_date')} className={SELECT_CLS} />
        {periodEnd && (
          <p className="mt-1.5 text-xs text-muted-foreground">
            Period ends: <span className="font-medium text-foreground">{fmtDate(periodEnd)}</span>
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Tax Rate (%)</label>
          <input type="number" min="0" max="100" step="0.01" value={form.tax_rate} onChange={set('tax_rate')} className={SELECT_CLS} />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Payment due (days after invoice)</label>
          <input type="number" min="1" max="365" value={form.due_days} onChange={set('due_days')} className={SELECT_CLS} />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          End Date <span className="text-muted-foreground text-xs">(optional)</span>
        </label>
        <input type="date" value={form.end_date} onChange={set('end_date')} className={SELECT_CLS} />
      </div>

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

// ── 3-dot Action Menu ─────────────────────────────────────────────────────────

function ActionMenu({ sub, onCancel, onPermanentDelete }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const btnRef = useRef(null)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (!btnRef.current?.contains(e.target) && !menuRef.current?.contains(e.target)) {
        setOpen(false)
      }
    }
    const onScroll = () => setOpen(false)
    document.addEventListener('mousedown', handler)
    document.addEventListener('scroll', onScroll, true)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('scroll', onScroll, true)
    }
  }, [open])

  const handleOpen = (e) => {
    e.stopPropagation()
    if (!btnRef.current) { setOpen((v) => !v); return }
    const rect = btnRef.current.getBoundingClientRect()
    setPos({ top: rect.bottom + 4, left: rect.right - 176 })
    setOpen((v) => !v)
  }

  const canCancel = !['cancelled', 'expired'].includes(sub.status)
  const canDelete = ['cancelled', 'expired'].includes(sub.status)

  return (
    <div>
      <button
        ref={btnRef}
        onClick={handleOpen}
        className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        title="Actions"
      >
        <EllipsisVerticalIcon className="w-4 h-4" />
      </button>
      {open && createPortal(
        <div
          ref={menuRef}
          style={{ top: pos.top, left: Math.max(4, pos.left) }}
          className="fixed w-44 bg-popover border border-border rounded-lg shadow-lg z-[9999] py-1 text-sm"
        >
          {canCancel && (
            <button
              onClick={(e) => { e.stopPropagation(); setOpen(false); onCancel(sub) }}
              className="w-full text-left px-3 py-2 text-foreground hover:bg-muted transition-colors"
            >
              Hủy subscription
            </button>
          )}
          {canDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); setOpen(false); onPermanentDelete(sub) }}
              className="w-full text-left px-3 py-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              Xóa vĩnh viễn
            </button>
          )}
        </div>,
        document.body
      )}
    </div>
  )
}

// ── Detail Panel ──────────────────────────────────────────────────────────────

function DetailRow({ label, children }) {
  return (
    <div className="flex justify-between items-start gap-4 py-2.5 border-b border-border last:border-0">
      <span className="text-sm text-muted-foreground flex-shrink-0 w-32">{label}</span>
      <span className="text-sm text-foreground text-right">{children}</span>
    </div>
  )
}

function SubscriptionDetail({ sub, service }) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Subscription</h3>
        <div>
          <DetailRow label="Organisation">{sub.org_name ?? sub.org_id}</DetailRow>
          <DetailRow label="Plan">{sub.plan_name ?? '—'}</DetailRow>
          <DetailRow label="Status"><StatusBadge status={sub.status} /></DetailRow>
          <DetailRow label="Billing Cycle">{CYCLE_LABELS[sub.billing_cycle] ?? sub.billing_cycle}</DetailRow>
          <DetailRow label="Start Date">{fmtDate(sub.start_date)}</DetailRow>
          <DetailRow label="Next Billing">{fmtDate(sub.next_billing_date) ?? '—'}</DetailRow>
          {sub.unit_price != null && (
            <DetailRow label="Unit Price">{fmtVND(sub.unit_price)}</DetailRow>
          )}
        </div>
      </div>

      {service ? (
        <div>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Linked Service</h3>
          <div>
            <DetailRow label="Name">{service.name}</DetailRow>
            <DetailRow label="Type"><TypeBadge type={service.type} /></DetailRow>
            <DetailRow label="Status"><StatusBadge status={service.status} /></DetailRow>
            {service.domain && <DetailRow label="Domain">{service.domain}</DetailRow>}
            {service.expiry_date && <DetailRow label="Expiry">{fmtDate(service.expiry_date)}</DetailRow>}
            {service.monthly_cost != null && (
              <DetailRow label="Monthly Cost">{fmtVND(service.monthly_cost)}</DetailRow>
            )}
          </div>
        </div>
      ) : (
        <div>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Linked Service</h3>
          <p className="text-sm text-muted-foreground">No service linked</p>
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SubscriptionsPage() {
  const addToast = useNotificationStore((s) => s.addToast)

  const [subscriptions, setSubscriptions] = useState([])
  const [serviceMap, setServiceMap] = useState(new Map())
  const [items, setItems] = useState([])
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [filterStatus, setFilterStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)

  const [createOpen, setCreateOpen] = useState(false)
  const [detailSub, setDetailSub] = useState(null)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const [permanentDeleteTarget, setPermanentDeleteTarget] = useState(null)
  const [deleteChecked, setDeleteChecked] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  // Reset page when filters change
  useEffect(() => { setPage(1) }, [filterStatus, debouncedSearch])

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError('')
      const params = { page, per_page: PER_PAGE }
      if (filterStatus !== 'all') params.status = filterStatus
      if (debouncedSearch) params.search = debouncedSearch
      const [subsData, itemsData, orgsData, servicesData] = await Promise.all([
        listSubscriptions(params),
        listItems(),
        listOrganizations({ per_page: 200 }),
        listServices(),
      ])
      setSubscriptions(Array.isArray(subsData?.items) ? subsData.items : [])
      setTotal(subsData?.total ?? 0)
      setPages(subsData?.pages ?? 1)
      setItems(Array.isArray(itemsData) ? itemsData : (itemsData?.items ?? []))
      setOrgs(Array.isArray(orgsData) ? orgsData : (orgsData?.items ?? []))
      const svcArr = Array.isArray(servicesData) ? servicesData : []
      const map = new Map()
      svcArr.forEach((s) => { if (s.subscription_id) map.set(s.subscription_id, s) })
      setServiceMap(map)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to load subscriptions')
    } finally {
      setLoading(false)
    }
  }, [filterStatus, page, debouncedSearch])

  useEffect(() => { load() }, [load])

  const handleCreate = async (form) => {
    setSaving(true)
    try {
      await createSubscription(form)
      setCreateOpen(false)
      addToast({ title: 'Đã tạo subscription + service đi kèm', type: 'success' })
      load()
    } catch (err) {
      throw err
    } finally {
      setSaving(false)
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

  const handlePermanentDelete = async () => {
    if (!permanentDeleteTarget || !deleteChecked) return
    setDeleting(true)
    try {
      await deleteSubscriptionPermanent(permanentDeleteTarget.id)
      setPermanentDeleteTarget(null)
      setDeleteChecked(false)
      addToast({ title: 'Subscription đã bị xóa vĩnh viễn', type: 'success' })
      load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to delete subscription')
      setPermanentDeleteTarget(null)
      setDeleteChecked(false)
    } finally {
      setDeleting(false)
    }
  }

  const linkedService = detailSub ? serviceMap.get(detailSub.id) : null

  return (
    <div className="p-6 max-w-7xl mx-auto">
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

      {/* Search + Filter bar */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by organisation…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
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
        {(filterStatus !== 'all' || search) && (
          <button
            onClick={() => { setFilterStatus('all'); setSearch('') }}
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
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Organisation</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Plan</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Service</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Billing</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Next Billing</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Price</th>
                <th className="px-4 py-3 w-10" />
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
            ) : subscriptions.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={8}>
                    <div className="flex flex-col items-center justify-center py-20 text-center">
                      <CreditCardIcon className="w-10 h-10 text-muted-foreground/40 mb-3" />
                      <p className="font-medium text-foreground">No subscriptions found</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        {search || filterStatus !== 'all' ? 'Try adjusting your filters' : 'Create one to get started'}
                      </p>
                    </div>
                  </td>
                </tr>
              </tbody>
            ) : (
              <tbody className="divide-y divide-border">
                {subscriptions.map((sub) => {
                  const svc = serviceMap.get(sub.id)
                  return (
                    <tr
                      key={sub.id}
                      onClick={() => setDetailSub(sub)}
                      className="hover:bg-muted/30 transition-colors cursor-pointer"
                    >
                      <td className="px-4 py-3 font-medium text-foreground">{sub.org_name ?? sub.org_id}</td>
                      <td className="px-4 py-3 text-foreground">{sub.plan_name ?? '—'}</td>
                      <td className="px-4 py-3">
                        {svc ? (
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-foreground leading-tight">{svc.name}</p>
                            {svc.domain && (
                              <p className="text-xs text-muted-foreground leading-tight">{svc.domain}</p>
                            )}
                            <TypeBadge type={svc.type} />
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={sub.status} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {CYCLE_LABELS[sub.billing_cycle] ?? sub.billing_cycle}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground tabular-nums">
                        {fmtDate(sub.next_billing_date) ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-foreground tabular-nums">
                        {sub.unit_price != null ? fmtVND(sub.unit_price) : '—'}
                      </td>
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <ActionMenu
                          sub={sub}
                          onCancel={setCancelTarget}
                          onPermanentDelete={(s) => { setPermanentDeleteTarget(s); setDeleteChecked(false) }}
                        />
                      </td>
                    </tr>
                  )
                })}
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

      {/* Detail Modal */}
      <Modal open={!!detailSub} onClose={() => setDetailSub(null)} title="Subscription Details">
        {detailSub && <SubscriptionDetail sub={detailSub} service={linkedService} />}
      </Modal>

      {/* Cancel Confirm Modal */}
      <Modal open={!!cancelTarget} onClose={() => setCancelTarget(null)} title="Hủy Subscription">
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Bạn có chắc muốn hủy subscription của{' '}
            <span className="font-semibold">{cancelTarget?.org_name ?? cancelTarget?.org_id}</span>
            {cancelTarget?.plan_name ? ` (${cancelTarget.plan_name})` : ''}?
            Hành động này không thể hoàn tác.
          </p>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => setCancelTarget(null)}
              className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Giữ nguyên
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {cancelling && <Spinner className="w-3.5 h-3.5" />}
              Hủy Subscription
            </button>
          </div>
        </div>
      </Modal>

      {/* Permanent Delete Confirm Modal (2-step) */}
      <Modal
        open={!!permanentDeleteTarget}
        onClose={() => { setPermanentDeleteTarget(null); setDeleteChecked(false) }}
        title="Xóa vĩnh viễn"
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-red-50 border border-red-200 dark:bg-red-900/20 dark:border-red-800 p-3 space-y-1">
            <p className="text-sm font-semibold text-red-700 dark:text-red-400">
              Hành động không thể hoàn tác
            </p>
            <p className="text-sm text-red-700 dark:text-red-400">
              Subscription và service đi kèm sẽ bị xóa vĩnh viễn. Hóa đơn được giữ lại.
            </p>
          </div>
          <p className="text-sm text-foreground">
            Bạn sắp xóa vĩnh viễn subscription của{' '}
            <span className="font-semibold">{permanentDeleteTarget?.org_name ?? permanentDeleteTarget?.org_id}</span>
            {permanentDeleteTarget?.plan_name ? ` (${permanentDeleteTarget.plan_name})` : ''}.
          </p>
          <label className="flex items-start gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={deleteChecked}
              onChange={(e) => setDeleteChecked(e.target.checked)}
              className="mt-0.5 rounded border-input accent-red-600"
            />
            <span className="text-sm text-foreground">
              Tôi hiểu rằng hành động này sẽ xóa vĩnh viễn subscription và service đi kèm.
            </span>
          </label>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => { setPermanentDeleteTarget(null); setDeleteChecked(false) }}
              className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Hủy bỏ
            </button>
            <button
              type="button"
              onClick={handlePermanentDelete}
              disabled={!deleteChecked || deleting}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {deleting && <Spinner className="w-3.5 h-3.5" />}
              Xóa vĩnh viễn
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

import { useState, useEffect, useRef, useCallback } from 'react'
import { PlusIcon, PencilIcon, CubeIcon } from '@heroicons/react/24/outline'
import { Modal } from '@/components/ui/Modal'
import {
  Button,
  EmptyState,
  LoadingState,
  MobileCardList,
  MobileDataCard,
  MobileDataRow,
  ResponsiveTableViewport,
  Spinner,
} from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import { listItems, createItem, updateItem } from '@/api/items'
import { formatCurrencyVND as fmtVND } from '@/lib/utils'
import { TYPE_COLORS, ITEM_STATUS_COLORS } from '@/lib/statusColors'
import { SEARCH_DEBOUNCE_MS, PAGE_SIZE } from '@/lib/constants'

const PER_PAGE = PAGE_SIZE

const EMPTY_FORM = { code: '', name: '', type: 'saas', unit_price: '', unit: 'month', description: '', is_active: true }

function ItemForm({ initial = EMPTY_FORM, onSubmit, onCancel, loading, isEdit }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setChecked = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.checked }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.code.trim()) { setError('Code is required'); return }
    if (!form.name.trim()) { setError('Name is required'); return }
    if (form.unit_price === '' || isNaN(Number(form.unit_price))) { setError('Unit price is required and must be a number'); return }
    try {
      await onSubmit({ ...form, unit_price: Number(form.unit_price) })
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

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Code <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.code}
            onChange={set('code')}
            placeholder="SVC-001"
            disabled={isEdit}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={set('name')}
            placeholder="Service name"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Type</label>
          <select
            value={form.type}
            onChange={set('type')}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="saas">SaaS</option>
            <option value="hosting">Hosting</option>
            <option value="domain">Domain</option>
            <option value="support">Support</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Unit</label>
          <input
            type="text"
            value={form.unit}
            onChange={set('unit')}
            placeholder="month"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Unit Price (VND) <span className="text-red-500">*</span>
        </label>
        <input
          type="number"
          min="0"
          step="1000"
          value={form.unit_price}
          onChange={set('unit_price')}
          placeholder="0"
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Description</label>
        <textarea
          value={form.description}
          onChange={set('description')}
          rows={2}
          placeholder="Optional description..."
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
        />
      </div>

      {isEdit && (
        <div className="flex items-center gap-3">
          <input
            id="is_active"
            type="checkbox"
            checked={form.is_active}
            onChange={setChecked('is_active')}
            className="w-4 h-4 rounded border-input accent-primary"
          />
          <label htmlFor="is_active" className="text-sm font-medium text-foreground cursor-pointer">
            Active
          </label>
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
          {isEdit ? 'Save Changes' : 'Create Item'}
        </button>
      </div>
    </form>
  )
}

export default function ItemsPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [filterType, setFilterType] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)

  // Bulk select
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  // Inline price edit: { itemId, value }
  const [editPrice, setEditPrice] = useState({ itemId: null, value: '' })
  const priceInputRef = useRef(null)

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [search])

  // Reset page when search, type or status filter changes; also clear selection
  useEffect(() => { setPage(1); setSelectedIds(new Set()) }, [debouncedSearch, filterType, filterStatus])

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError('')
      const params = { paginated: true, page, per_page: PER_PAGE }
      if (debouncedSearch) params.search = debouncedSearch
      if (filterType !== 'all') params.type = filterType
      if (filterStatus === 'active') params.is_active = true
      if (filterStatus === 'inactive') params.is_active = false
      const data = await listItems(params)
      const allItems = Array.isArray(data?.items) ? data.items : []
      setItems(allItems)
      setTotal(data?.total ?? 0)
      setPages(data?.pages ?? 1)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to load items')
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, filterType, filterStatus, page])

  useEffect(() => { load() }, [load])

  // Focus price input when edit starts
  useEffect(() => {
    if (editPrice.itemId !== null && priceInputRef.current) {
      priceInputRef.current.focus()
      priceInputRef.current.select()
    }
  }, [editPrice.itemId])

  const handleCreate = async (form) => {
    setSaving(true)
    try {
      await createItem(form)
      setCreateOpen(false)
      load()
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = async (form) => {
    setSaving(true)
    try {
      await updateItem(editItem.id, form)
      setEditItem(null)
      load()
    } finally {
      setSaving(false)
    }
  }

  // Inline price save
  const savePriceEdit = async (item) => {
    const newPrice = Number(editPrice.value)
    if (isNaN(newPrice) || newPrice < 0) {
      setEditPrice({ itemId: null, value: '' })
      return
    }
    if (newPrice === item.unit_price) {
      setEditPrice({ itemId: null, value: '' })
      return
    }
    try {
      await updateItem(item.id, { unit_price: newPrice })
      setEditPrice({ itemId: null, value: '' })
      load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to update price')
      setEditPrice({ itemId: null, value: '' })
    }
  }

  // Bulk selection helpers
  const allSelected = items.length > 0 && selectedIds.size === items.length
  const someSelected = selectedIds.size > 0

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)))
    }
  }

  const toggleSelectOne = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleBulkActivate = async () => {
    setBulkLoading(true)
    try {
      await Promise.all([...selectedIds].map((id) => updateItem(id, { is_active: true })))
      setSelectedIds(new Set())
      load()
    } finally {
      setBulkLoading(false)
    }
  }

  const handleBulkDeactivate = async () => {
    setBulkLoading(true)
    try {
      await Promise.all([...selectedIds].map((id) => updateItem(id, { is_active: false })))
      setSelectedIds(new Set())
      load()
    } finally {
      setBulkLoading(false)
    }
  }

  const hasActiveFilter = search || filterType !== 'all' || filterStatus !== 'all'

  return (
    <div className="px-4 py-5 sm:p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Items</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage your service catalog</p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <PlusIcon className="w-4 h-4" />
          Create Item
        </button>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by code or name…"
          className="flex-1 max-w-xs px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All types</option>
          <option value="saas">SaaS</option>
          <option value="hosting">Hosting</option>
          <option value="domain">Domain</option>
          <option value="support">Support</option>
          <option value="other">Other</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        {hasActiveFilter && (
          <button
            onClick={() => { setSearch(''); setFilterType('all'); setFilterStatus('all') }}
            className="px-3 py-2 border border-input rounded-lg bg-background text-muted-foreground text-sm hover:text-foreground hover:bg-muted transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {/* Bulk actions toolbar */}
        {someSelected && (
          <div className="flex items-center gap-2 px-4 py-2 bg-primary/5 border-b border-border">
            <span className="text-xs text-muted-foreground mr-1">
              {selectedIds.size} selected
            </span>
            <button
              onClick={handleBulkActivate}
              disabled={bulkLoading}
              className="px-3 py-1.5 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 flex items-center gap-1.5 transition-colors"
            >
              {bulkLoading && <Spinner className="w-3 h-3" />}
              Activate selected
            </button>
            <button
              onClick={handleBulkDeactivate}
              disabled={bulkLoading}
              className="px-3 py-1.5 rounded-md text-xs font-medium bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50 flex items-center gap-1.5 transition-colors"
            >
              {bulkLoading && <Spinner className="w-3 h-3" />}
              Deactivate selected
            </button>
          </div>
        )}

        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} className="border-t-0 border-b border-border" />
        <ResponsiveTableViewport
          mobile={loading ? (
            <LoadingState rows={3} label="Loading items" />
          ) : items.length === 0 ? (
            <EmptyState icon={CubeIcon} title="No items yet" description="Create one to get started." />
          ) : (
            <MobileCardList ariaLabel="Items">
              {items.map((item) => (
                <MobileDataCard
                  key={item.id}
                  onClick={() => setEditItem(item)}
                  ariaLabel={`Edit ${item.name}`}
                  actions={(
                    <>
                      <label className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground" onClick={(event) => event.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="h-5 w-5 accent-primary"
                          checked={selectedIds.has(item.id)}
                          onChange={() => toggleSelectOne(item.id)}
                        />
                        Select
                      </label>
                      <Button type="button" size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); setEditItem(item) }}>
                        Edit item
                      </Button>
                    </>
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate text-base font-semibold text-foreground" title={item.name}>{item.name}</h3>
                      <p className="mt-0.5 font-mono text-xs text-muted-foreground">{item.code}</p>
                    </div>
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${ITEM_STATUS_COLORS[String(item.is_active)] ?? 'bg-muted text-muted-foreground'}`}>
                      {item.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <dl className="mt-3 divide-y divide-border">
                    <MobileDataRow label="Type">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize ${TYPE_COLORS[item.type] ?? 'bg-muted text-muted-foreground'}`}>{item.type}</span>
                    </MobileDataRow>
                    <MobileDataRow label="Unit price">{fmtVND(item.unit_price)}</MobileDataRow>
                    <MobileDataRow label="Unit">{item.unit}</MobileDataRow>
                  </dl>
                </MobileDataCard>
              ))}
            </MobileCardList>
          )}
        >
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-3 w-10">
                <input
                  type="checkbox"
                  disabled={loading}
                  className="w-4 h-4 accent-primary"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                />
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Code</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Name</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Type</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Unit Price</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Unit</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          {loading ? (
            <tbody>
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-border">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 skeleton-shimmer rounded" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : items.length === 0 ? (
            <tbody>
              <tr>
                <td colSpan={8}>
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <CubeIcon className="w-10 h-10 text-muted-foreground mb-3" />
                    <p className="font-medium text-foreground">No items yet</p>
                    <p className="text-sm text-muted-foreground mt-1">Create one to get started</p>
                  </div>
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody className="divide-y divide-border">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="hover:bg-muted/30 transition-colors cursor-pointer"
                  onClick={() => {
                    // Don't open edit modal if we're editing a price cell
                    if (editPrice.itemId === item.id) return
                    setEditItem(item)
                  }}
                >
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="w-4 h-4 accent-primary"
                      checked={selectedIds.has(item.id)}
                      onChange={() => toggleSelectOne(item.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{item.code}</td>
                  <td className="px-4 py-3 font-medium text-foreground">{item.name}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${TYPE_COLORS[item.type] ?? 'bg-muted text-muted-foreground'}`}>
                      {item.type}
                    </span>
                  </td>
                  <td
                    className="px-4 py-3 text-foreground tabular-nums"
                    onClick={(e) => {
                      e.stopPropagation()
                      if (editPrice.itemId !== item.id) {
                        setEditPrice({ itemId: item.id, value: String(item.unit_price) })
                      }
                    }}
                  >
                    {editPrice.itemId === item.id ? (
                      <input
                        ref={priceInputRef}
                        type="number"
                        min="0"
                        step="1000"
                        value={editPrice.value}
                        onChange={(e) => setEditPrice((p) => ({ ...p, value: e.target.value }))}
                        onBlur={() => savePriceEdit(item)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') { e.preventDefault(); savePriceEdit(item) }
                          if (e.key === 'Escape') { e.preventDefault(); setEditPrice({ itemId: null, value: '' }) }
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-28 px-2 py-1 border border-ring rounded bg-background text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-ring tabular-nums"
                      />
                    ) : (
                      <span className="cursor-text hover:underline decoration-dotted underline-offset-2" title="Click to edit price">
                        {fmtVND(item.unit_price)}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{item.unit}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${ITEM_STATUS_COLORS[String(item.is_active)] ?? 'bg-muted text-muted-foreground'}`}>
                      {item.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => { e.stopPropagation(); setEditItem(item) }}
                      className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                    >
                      <PencilIcon className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
        </ResponsiveTableViewport>
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
      </div>

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Item">
        <ItemForm
          onSubmit={handleCreate}
          onCancel={() => setCreateOpen(false)}
          loading={saving}
          isEdit={false}
        />
      </Modal>

      {/* Edit Modal */}
      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Edit Item">
        {editItem && (
          <ItemForm
            initial={{
              code: editItem.code,
              name: editItem.name,
              type: editItem.type,
              unit_price: editItem.unit_price,
              unit: editItem.unit ?? 'month',
              description: editItem.description ?? '',
              is_active: editItem.is_active,
            }}
            onSubmit={handleEdit}
            onCancel={() => setEditItem(null)}
            loading={saving}
            isEdit
          />
        )}
      </Modal>
    </div>
  )
}

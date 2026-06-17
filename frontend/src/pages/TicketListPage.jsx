import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getTickets, deleteTicket, deleteTicketPermanent } from '@/api/tickets'
import { useRole } from '@/hooks/useRole'
import { Spinner } from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import { formatDateTime } from '@/lib/utils'
import { PAGE_SIZE } from '@/lib/constants'
import {
  PlusIcon,
  MagnifyingGlassIcon,
  TicketIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'

const STATUSES = ['All', 'Open', 'In Progress', 'Waiting', 'Resolved', 'Closed']
const PRIORITIES = ['All', 'Urgent', 'High', 'Medium', 'Low']

const STATUS_STYLES = {
  Open:          'bg-blue-50 text-blue-700',
  'In Progress': 'bg-amber-50 text-amber-700',
  Waiting:       'bg-purple-50 text-purple-700',
  Resolved:      'bg-green-50 text-green-700',
  Closed:        'bg-gray-100 text-gray-500',
}

const PRIORITY_STYLES = {
  Urgent: 'bg-red-50 text-red-700',
  High:   'bg-orange-50 text-orange-700',
  Medium: 'bg-yellow-50 text-yellow-700',
  Low:    'bg-gray-100 text-gray-500',
}

function StatusBadge({ label }) {
  const cls = STATUS_STYLES[label] ?? 'bg-gray-100 text-gray-500'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

function PriorityBadge({ label }) {
  const cls = PRIORITY_STYLES[label] ?? 'bg-gray-100 text-gray-500'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

const PER_PAGE = PAGE_SIZE

export default function TicketListPage() {
  const { isCustomer, isAdmin } = useRole()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [searchInput, setSearchInput] = useState(searchParams.get('q') ?? '')
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('q') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? 'All')
  const [priority, setPriority] = useState(searchParams.get('priority') ?? 'All')
  const [page, setPage] = useState(Number(searchParams.get('page') ?? 1))

  const [tickets, setTickets] = useState([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  // Context menu state
  const [ctxMenu, setCtxMenu] = useState(null) // { ticket, x, y }

  // Close context menu on outside mousedown (covers left + right + middle click)
  useEffect(() => {
    if (!ctxMenu) return
    const close = () => setCtxMenu(null)
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [ctxMenu])

  // Debounce search input → resets page to 1
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(searchInput)
      setPage(1)
    }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const handleStatusChange = useCallback((s) => {
    setStatus(s)
    setPage(1)
  }, [])

  const handlePriorityChange = useCallback((p) => {
    setPriority(p)
    setPage(1)
  }, [])

  // Server-side fetch
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const params = { page, per_page: PER_PAGE }
    if (debouncedSearch) params.search = debouncedSearch
    if (status !== 'All') params.status = status
    if (priority !== 'All') params.priority = priority

    getTickets(params)
      .then((data) => {
        if (cancelled) return
        setTickets(data.items)
        setTotal(data.total)
        setPages(data.pages)
        setLoading(false)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || 'Failed to load tickets')
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [debouncedSearch, status, priority, page, reloadKey])

  // Sync URL params
  useEffect(() => {
    const p = new URLSearchParams()
    if (debouncedSearch) p.set('q', debouncedSearch)
    if (status !== 'All') p.set('status', status)
    if (priority !== 'All') p.set('priority', priority)
    if (page > 1) p.set('page', String(page))
    setSearchParams(p, { replace: true })
  }, [debouncedSearch, status, priority, page, setSearchParams])

  const hasFilters = searchInput !== '' || status !== 'All' || priority !== 'All'

  const clearFilters = useCallback(() => {
    setSearchInput('')
    setDebouncedSearch('')
    setStatus('All')
    setPriority('All')
    setPage(1)
  }, [])

  const handleSoftDelete = useCallback(async (ticket) => {
    if (!window.confirm(`Xóa ticket #${ticket.id} "${ticket.subject}"?\n\nTicket sẽ bị ẩn (soft delete).`)) return
    try {
      await deleteTicket(ticket.id)
      setReloadKey(k => k + 1)
    } catch (err) {
      alert(err.message || 'Xóa thất bại')
    }
  }, [])

  const handleHardDelete = useCallback(async (ticket) => {
    if (!window.confirm(`XÓA VĨNH VIỄN ticket #${ticket.id} "${ticket.subject}"?\n\nHành động này KHÔNG thể hoàn tác. Toàn bộ file đính kèm sẽ bị xóa khỏi server.`)) return
    if (!window.confirm(`Xác nhận lần 2: Xóa vĩnh viễn #${ticket.id}?`)) return
    try {
      await deleteTicketPermanent(ticket.id)
      setReloadKey(k => k + 1)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Xóa thất bại'
      alert(detail)
    }
  }, [])

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Page header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="page-title">Support Tickets</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              {loading ? '…' : `${total} ticket${total !== 1 ? 's' : ''}`}
            </p>
          </div>
          <Link
            to="/tickets/new"
            className="btn-primary"
          >
            <PlusIcon className="w-4 h-4" />
            New Ticket
          </Link>
        </div>

        {/* Status tab bar */}
        <div className="flex gap-0 mt-4 -mb-px overflow-x-auto">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => handleStatusChange(s)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                status === s
                  ? 'border-gray-900 text-gray-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Search + filter bar */}
      <div className="bg-white border-b border-gray-100 px-6 py-2.5">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search input */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Search tickets..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-9 pr-8 py-1.5 text-sm border border-gray-200 rounded-lg bg-gray-50 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900/20 focus:border-gray-400 transition"
            />
            {searchInput && (
              <button
                onClick={() => setSearchInput('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Clear search"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Priority filter */}
          <select
            value={priority}
            onChange={(e) => handlePriorityChange(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg bg-gray-50 text-gray-700 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-gray-900/20 focus:border-gray-400 transition"
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p === 'All' ? 'All Priorities' : p}
              </option>
            ))}
          </select>

          {/* Clear filters link */}
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="text-sm text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors"
            >
              Clear filters
            </button>
          )}

          {/* Result count */}
          {!loading && (
            <span className="text-xs text-gray-400 ml-auto">
              {total === 0
                ? 'No tickets found'
                : `Showing ${tickets.length} of ${total}`}
            </span>
          )}
        </div>
      </div>

      {/* Context menu */}
      {ctxMenu && (
        <div
          className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[160px] text-sm"
          style={{ top: ctxMenu.y, left: ctxMenu.x }}
          onClick={e => e.stopPropagation()}
          onMouseDown={e => e.stopPropagation()}
        >
          <button
            className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700"
            onClick={() => { navigate(`/tickets/${ctxMenu.ticket.id}`); setCtxMenu(null) }}
          >
            Mở
          </button>
          {isAdmin && (
            <button
              className="w-full text-left px-4 py-2 hover:bg-red-50 text-red-600"
              onClick={() => { handleSoftDelete(ctxMenu.ticket); setCtxMenu(null) }}
            >
              Xóa ticket
            </button>
          )}
          {isAdmin && ['Resolved', 'Closed'].includes(ctxMenu.ticket.status) && (
            <button
              className="w-full text-left px-4 py-2 hover:bg-red-100 text-red-700 font-semibold border-t border-red-100 mt-1"
              onClick={() => { handleHardDelete(ctxMenu.ticket); setCtxMenu(null) }}
            >
              Xóa vĩnh viễn
            </button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Spinner className="w-5 h-5" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <TicketIcon className="w-10 h-10 text-gray-200" />
            <p className="text-sm font-medium text-gray-500">Could not load tickets</p>
            <p className="text-xs text-gray-400">{error}</p>
            <button
              onClick={() => setReloadKey((k) => k + 1)}
              className="mt-1 btn-primary"
            >
              Retry
            </button>
          </div>
        ) : tickets.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <TicketIcon className="w-10 h-10 text-gray-200" />
            <p className="text-sm font-medium text-gray-400">No tickets found</p>
            <p className="text-xs text-gray-300">
              {hasFilters ? 'Try a different search or clear filters.' : 'Create your first support ticket.'}
            </p>
            {!hasFilters && (
              <Link
                to="/tickets/new"
                className="mt-1 btn-primary"
              >
                <PlusIcon className="w-4 h-4" /> New Ticket
              </Link>
            )}
          </div>
        ) : (
          <>
            <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} className="border-t-0 border-b border-border" />
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-6 py-2.5 w-24">#</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5">Subject</th>
                  {!isCustomer && (
                    <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5 w-36">Org</th>
                  )}
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5 w-36">Service</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5 w-28">Status</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5 w-24">Priority</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-6 py-2.5 w-36">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 bg-white">
                {tickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    className="hover:bg-gray-50 transition-colors group cursor-pointer"
                    onClick={e => { if (e.target.closest('a')) return; navigate(`/tickets/${ticket.id}`) }}
                    onContextMenu={e => {
                      e.preventDefault()
                      e.stopPropagation()
                      const menuW = 180, menuH = 120
                      const x = e.clientX + menuW > window.innerWidth ? e.clientX - menuW : e.clientX
                      const y = e.clientY + menuH > window.innerHeight ? e.clientY - menuH : e.clientY
                      setCtxMenu({ ticket, x, y })
                    }}
                  >
                    <td className="px-6 py-3">
                      <Link to={`/tickets/${ticket.id}`} className="block">
                        <span className="text-xs font-mono text-gray-400 group-hover:text-gray-900 transition-colors">
                          #{ticket.id}
                        </span>
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <Link to={`/tickets/${ticket.id}`} className="block">
                        <span className="text-sm font-medium text-gray-800 group-hover:text-gray-900 transition-colors line-clamp-1">
                          {ticket.subject}
                        </span>
                      </Link>
                    </td>
                    {!isCustomer && (
                      <td className="px-3 py-3">
                        <Link to={`/tickets/${ticket.id}`} className="block">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-xs text-gray-700 font-medium line-clamp-1">
                              {ticket.org_name ?? `Org #${ticket.org_id}`}
                            </span>
                            {ticket.org_code && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gray-100 text-gray-500 font-mono flex-shrink-0">
                                {ticket.org_code}
                              </span>
                            )}
                          </div>
                        </Link>
                      </td>
                    )}
                    <td className="px-3 py-3">
                      <Link to={`/tickets/${ticket.id}`} className="block">
                        {ticket.service_name ? (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-xs text-gray-600 line-clamp-1">{ticket.service_name}</span>
                            {ticket.service_type && (
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0 ${
                                ticket.service_type === 'saas'    ? 'bg-violet-100 text-violet-700' :
                                ticket.service_type === 'hosting' ? 'bg-blue-100 text-blue-700'   :
                                ticket.service_type === 'domain'  ? 'bg-purple-100 text-purple-700' :
                                ticket.service_type === 'support' ? 'bg-orange-100 text-orange-700' :
                                'bg-gray-100 text-gray-600'
                              }`}>
                                {ticket.service_type === 'saas'    ? 'SaaS'    :
                                 ticket.service_type === 'hosting' ? 'Hosting' :
                                 ticket.service_type === 'domain'  ? 'Domain'  :
                                 ticket.service_type === 'support' ? 'Support' :
                                 ticket.service_type}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <Link to={`/tickets/${ticket.id}`} className="block">
                        <StatusBadge label={ticket.status} />
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <Link to={`/tickets/${ticket.id}`} className="block">
                        <PriorityBadge label={ticket.priority} />
                      </Link>
                    </td>
                    <td className="px-6 py-3">
                      <Link to={`/tickets/${ticket.id}`} className="block">
                        <span className="text-xs text-gray-400">{formatDateTime(ticket.created_at)}</span>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
          </>
        )}
      </div>
    </div>
  )
}

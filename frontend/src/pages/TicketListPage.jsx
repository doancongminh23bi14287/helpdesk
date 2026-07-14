import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { PlusIcon } from '@heroicons/react/24/outline'

import {
  archiveTicket,
  deleteTicket,
  deleteTicketPermanent,
  getTickets,
  unarchiveTicket,
} from '@/api/tickets'
import { listOrganizations } from '@/api/organizations'
import { useRole } from '@/hooks/useRole'
import { PageHeader } from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import { PAGE_SIZE } from '@/lib/constants'
import { TicketStatusTabs } from '@/components/tickets/TicketStatusTabs'
import { TicketFilterBar } from '@/components/tickets/TicketFilterBar'
import { TicketActionMenu, TicketTable } from '@/components/tickets/TicketTable'

const PER_PAGE = PAGE_SIZE

export default function TicketListPage() {
  const { isCustomer, isAdmin } = useRole()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [searchInput, setSearchInput] = useState(searchParams.get('q') ?? '')
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('q') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? 'All')
  const [priority, setPriority] = useState(searchParams.get('priority') ?? 'All')
  const [organizationId, setOrganizationId] = useState(searchParams.get('org_id') ?? '')
  const [page, setPage] = useState(Number(searchParams.get('page') ?? 1))
  const [showArchived, setShowArchived] = useState(searchParams.get('archived') === '1')

  const [organizations, setOrganizations] = useState([])
  const [tickets, setTickets] = useState([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [actionMenu, setActionMenu] = useState(null)

  useEffect(() => {
    if (isCustomer) return
    let active = true
    listOrganizations({ per_page: 100 })
      .then((data) => {
        if (!active) return
        setOrganizations(Array.isArray(data) ? data : (data?.items ?? []))
      })
      .catch(() => {})
    return () => { active = false }
  }, [isCustomer])

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim())
      setPage(1)
    }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  const handleStatusChange = useCallback((nextStatus) => {
    setStatus(nextStatus)
    setPage(1)
  }, [])

  const handlePriorityChange = useCallback((nextPriority) => {
    setPriority(nextPriority)
    setPage(1)
  }, [])

  const handleOrganizationChange = useCallback((nextOrganization) => {
    setOrganizationId(nextOrganization)
    setPage(1)
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const params = { page, per_page: PER_PAGE }
    if (debouncedSearch) params.search = debouncedSearch
    if (status !== 'All') params.status = status
    if (priority !== 'All') params.priority = priority
    if (!isCustomer && organizationId) params.org_id = Number(organizationId)
    if (isCustomer && showArchived) params.archived = true

    getTickets(params)
      .then((data) => {
        if (cancelled) return
        setTickets(data.items)
        setTotal(data.total)
        setPages(data.pages)
      })
      .catch((requestError) => {
        if (cancelled) return
        setError(requestError.message || 'Failed to load tickets')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [debouncedSearch, status, priority, organizationId, page, reloadKey, isCustomer, showArchived])

  useEffect(() => {
    const params = new URLSearchParams()
    if (debouncedSearch) params.set('q', debouncedSearch)
    if (status !== 'All') params.set('status', status)
    if (priority !== 'All') params.set('priority', priority)
    if (!isCustomer && organizationId) params.set('org_id', organizationId)
    if (page > 1) params.set('page', String(page))
    if (showArchived) params.set('archived', '1')
    setSearchParams(params, { replace: true })
  }, [debouncedSearch, status, priority, organizationId, page, showArchived, isCustomer, setSearchParams])

  const hasFilters = Boolean(
    searchInput || status !== 'All' || priority !== 'All' || (!isCustomer && organizationId),
  )

  const clearFilters = useCallback(() => {
    setSearchInput('')
    setDebouncedSearch('')
    setStatus('All')
    setPriority('All')
    setOrganizationId('')
    setPage(1)
  }, [])

  const refresh = useCallback(() => setReloadKey((key) => key + 1), [])
  const openTicket = useCallback((ticket) => navigate(`/tickets/${ticket.id}`), [navigate])
  const closeActionMenu = useCallback(() => setActionMenu(null), [])
  const openActionMenu = useCallback((ticket, x, y) => setActionMenu({ ticket, x, y }), [])

  const handleSoftDelete = useCallback(async (ticket) => {
    if (!window.confirm(`Delete ticket #${ticket.id} "${ticket.subject}"? The ticket will be hidden.`)) return
    try {
      await deleteTicket(ticket.id)
      refresh()
    } catch (requestError) {
      window.alert(requestError.message || 'Delete failed')
    }
  }, [refresh])

  const handleArchiveToggle = useCallback(async (ticket) => {
    try {
      if (showArchived) await unarchiveTicket(ticket.id)
      else await archiveTicket(ticket.id)
      refresh()
    } catch (requestError) {
      window.alert(requestError.response?.data?.detail || requestError.message || 'Action failed')
    }
  }, [refresh, showArchived])

  const handleHardDelete = useCallback(async (ticket) => {
    if (!window.confirm(`Permanently delete ticket #${ticket.id} "${ticket.subject}" and all of its attachments?`)) return
    if (!window.confirm(`Confirm permanent deletion of ticket #${ticket.id}. This cannot be undone.`)) return
    try {
      await deleteTicketPermanent(ticket.id)
      refresh()
    } catch (requestError) {
      window.alert(requestError.response?.data?.detail || requestError.message || 'Delete failed')
    }
  }, [refresh])

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <header className="border-b border-border bg-surface px-4 pt-4 sm:px-6">
        <PageHeader
          title="Support Tickets"
          description={loading ? 'Loading tickets...' : `${total} ticket${total !== 1 ? 's' : ''}`}
          actions={(
            <Link to="/tickets/new" className="btn-primary">
              <PlusIcon className="h-4 w-4" aria-hidden="true" />
              New Ticket
            </Link>
          )}
        />
        <div className="mt-3">
          <TicketStatusTabs value={status} onChange={handleStatusChange} />
        </div>
      </header>

      <TicketFilterBar
        search={searchInput}
        onSearchChange={setSearchInput}
        priority={priority}
        onPriorityChange={handlePriorityChange}
        organizations={organizations}
        organizationId={organizationId}
        onOrganizationChange={handleOrganizationChange}
        showOrganization={!isCustomer}
        showArchived={showArchived}
        onToggleArchived={() => { setShowArchived((value) => !value); setPage(1) }}
        showArchiveToggle={isCustomer}
        hasFilters={hasFilters}
        onClear={clearFilters}
        loading={loading}
        shown={tickets.length}
        total={total}
      />

      <main className="min-h-0 flex-1 overflow-y-auto">
        {pages > 1 && !loading && !error && (
          <Pagination
            page={page}
            pages={pages}
            total={total}
            perPage={PER_PAGE}
            onPage={setPage}
            className="border-t-0 border-b border-border"
          />
        )}

        <TicketTable
          tickets={tickets}
          loading={loading}
          error={error}
          hasFilters={hasFilters}
          showOrganization={!isCustomer}
          onOpen={openTicket}
          onOpenMenu={openActionMenu}
          onRetry={refresh}
        />

        {pages > 1 && !loading && !error && tickets.length > 0 && (
          <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
        )}
      </main>

      <TicketActionMenu
        menu={actionMenu}
        onClose={closeActionMenu}
        isCustomer={isCustomer}
        isAdmin={isAdmin}
        showArchived={showArchived}
        onArchive={handleArchiveToggle}
        onSoftDelete={handleSoftDelete}
        onHardDelete={handleHardDelete}
        onOpen={openTicket}
      />
    </div>
  )
}

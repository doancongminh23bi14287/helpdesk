import { useEffect, useRef } from 'react'
import {
  EllipsisVerticalIcon,
  InboxIcon,
  TicketIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  NoSearchResults,
  PriorityBadge,
  StatusBadge,
} from '@/components/ui'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'

function assigneeLabel(ticket) {
  if (ticket.assignee_name) return ticket.assignee_name
  const primary = ticket.assignees?.find((item) => item.is_primary) || ticket.assignees?.[0]
  return primary?.full_name || primary?.email || 'Unassigned'
}

function TicketIdentity({ ticket }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-muted-foreground">#{ticket.id}</span>
        {ticket.ticket_type && <span className="truncate text-xs text-muted-foreground">{ticket.ticket_type}</span>}
        {ticket.source && <span className="text-xs capitalize text-muted-foreground">{ticket.source}</span>}
      </div>
      <p className="mt-1 truncate text-sm font-semibold text-foreground" title={ticket.subject}>
        {ticket.subject}
      </p>
    </div>
  )
}

function OrganizationService({ ticket, showOrganization }) {
  return (
    <div className="min-w-0 space-y-0.5">
      {showOrganization && (
        <p className="truncate text-sm font-medium text-foreground" title={ticket.org_name || undefined}>
          {ticket.org_name || `Organization #${ticket.org_id}`}
        </p>
      )}
      <p className="truncate text-xs text-muted-foreground" title={ticket.service_name || undefined}>
        {ticket.service_name || 'No service linked'}
      </p>
    </div>
  )
}

function Assignee({ ticket }) {
  const label = assigneeLabel(ticket)
  const unassigned = label === 'Unassigned'
  return (
    <div className={cn('flex min-w-0 items-center gap-1.5 text-xs', unassigned ? 'text-warning' : 'text-secondary-foreground')}>
      <UserCircleIcon className="h-4 w-4 flex-none" aria-hidden="true" />
      <span className="truncate" title={label}>{label}</span>
    </div>
  )
}

function SlaIndicator({ ticket }) {
  if (!ticket.sla_state || ['unknown', 'green', 'met'].includes(ticket.sla_state)) return null
  const label = ticket.sla_state === 'breached' ? 'SLA breached' : 'SLA at risk'
  return <span className={cn('text-[11px] font-medium', ticket.sla_state === 'breached' ? 'text-danger' : 'text-warning')}>{label}</span>
}

function MoreButton({ ticket, onOpenMenu }) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation()
        const box = event.currentTarget.getBoundingClientRect()
        onOpenMenu(ticket, box.right - 176, box.bottom + 4)
      }}
      className="rounded-md p-1.5 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
      aria-label={`More actions for ticket #${ticket.id}`}
    >
      <EllipsisVerticalIcon className="h-4 w-4" aria-hidden="true" />
    </button>
  )
}

function DesktopTable({ tickets, showOrganization, onOpen, onOpenMenu }) {
  return (
    <div className="hidden overflow-x-auto md:block">
      <table className="w-full min-w-[880px]">
        <thead className="border-b border-border bg-surface-muted/70">
          <tr>
            <th className="table-header px-5 py-3 text-left">Ticket</th>
            <th className="table-header px-4 py-3 text-left">Organization / Service</th>
            <th className="table-header px-4 py-3 text-left">Status</th>
            <th className="table-header px-4 py-3 text-left">Priority</th>
            <th className="table-header px-4 py-3 text-left">Assignee</th>
            <th className="table-header px-4 py-3 text-left">Updated</th>
            <th className="w-12 px-3 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {tickets.map((ticket) => (
            <tr
              key={ticket.id}
              tabIndex={0}
              role="link"
              aria-label={`Open ticket #${ticket.id}: ${ticket.subject}`}
              onClick={(event) => {
                if (event.target.closest('button, a, input, select')) return
                onOpen(ticket)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onOpen(ticket)
                }
              }}
              onContextMenu={(event) => {
                event.preventDefault()
                onOpenMenu(ticket, event.clientX, event.clientY)
              }}
              className="cursor-pointer transition-colors hover:bg-surface-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
            >
              <td className="max-w-[320px] px-5 py-3.5"><TicketIdentity ticket={ticket} /></td>
              <td className="max-w-[220px] px-4 py-3.5"><OrganizationService ticket={ticket} showOrganization={showOrganization} /></td>
              <td className="px-4 py-3.5"><StatusBadge status={ticket.status} /></td>
              <td className="px-4 py-3.5"><PriorityBadge priority={ticket.priority} /></td>
              <td className="max-w-[170px] px-4 py-3.5"><Assignee ticket={ticket} /></td>
              <td className="px-4 py-3.5">
                <p className="whitespace-nowrap text-xs text-secondary-foreground">{formatDateTime(ticket.updated_at || ticket.created_at)}</p>
                <SlaIndicator ticket={ticket} />
              </td>
              <td className="px-3 py-3.5"><MoreButton ticket={ticket} onOpenMenu={onOpenMenu} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MobileCards({ tickets, showOrganization, onOpen, onOpenMenu }) {
  return (
    <div className="space-y-2.5 bg-background px-3 pb-4 md:hidden">
      {tickets.map((ticket) => {
        const assignee = assigneeLabel(ticket)
        const unassigned = assignee === 'Unassigned'
        return (
          <article
            key={ticket.id}
            tabIndex={0}
            role="link"
            onClick={(event) => {
              if (event.target.closest('button, a')) return
              onOpen(ticket)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onOpen(ticket)
              }
            }}
            className="cursor-pointer rounded-lg border border-border bg-surface p-4 shadow-sm transition active:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={'Open ticket #' + ticket.id + ': ' + ticket.subject}
          >
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  <span className="font-mono font-medium text-secondary-foreground">#{ticket.id}</span>
                  {ticket.ticket_type && <span>{ticket.ticket_type}</span>}
                  {ticket.source && <span className="capitalize">{ticket.source}</span>}
                </div>
                <h2 className="mt-1.5 line-clamp-2 text-[15px] font-semibold leading-5 text-foreground">
                  {ticket.subject}
                </h2>
              </div>
              <MoreButton ticket={ticket} onOpenMenu={onOpenMenu} />
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge status={ticket.status} />
              <PriorityBadge priority={ticket.priority} />
              <SlaIndicator ticket={ticket} />
            </div>

            <div className="mt-3 border-t border-border pt-3">
              {showOrganization && (
                <p className="truncate text-sm font-medium text-foreground" title={ticket.org_name || undefined}>
                  {ticket.org_name || 'Organization #' + ticket.org_id}
                </p>
              )}
              <div className="mt-1 flex min-w-0 items-center justify-between gap-3">
                <p className="min-w-0 truncate text-xs text-muted-foreground" title={ticket.service_name || undefined}>
                  {ticket.service_name || 'No service linked'}
                </p>
                <div className={cn('flex min-w-0 max-w-[48%] items-center gap-1.5 text-xs', unassigned ? 'text-warning' : 'text-secondary-foreground')}>
                  <UserCircleIcon className="h-4 w-4 flex-none" aria-hidden="true" />
                  <span className="truncate">{assignee}</span>
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Updated {formatDateTime(ticket.updated_at || ticket.created_at)}
              </p>
            </div>
          </article>
        )
      })}
    </div>
  )
}

export function TicketTable({
  tickets,
  loading,
  error,
  hasFilters,
  showOrganization,
  onOpen,
  onOpenMenu,
  onRetry,
}) {
  if (loading) return <LoadingState label="Loading tickets" rows={6} />
  if (error) return <ErrorState title="Could not load tickets" description={error} onRetry={onRetry} />
  if (tickets.length === 0 && hasFilters) return <NoSearchResults onClear={undefined} />
  if (tickets.length === 0) {
    return (
      <EmptyState
        icon={InboxIcon}
        title="No tickets yet"
        description="Create a support ticket to start a conversation with the support team."
      />
    )
  }

  return (
    <>
      <DesktopTable tickets={tickets} showOrganization={showOrganization} onOpen={onOpen} onOpenMenu={onOpenMenu} />
      <MobileCards tickets={tickets} showOrganization={showOrganization} onOpen={onOpen} onOpenMenu={onOpenMenu} />
    </>
  )
}

export function TicketActionMenu({
  menu,
  onClose,
  isCustomer,
  isAdmin,
  showArchived,
  onArchive,
  onSoftDelete,
  onHardDelete,
  onOpen,
}) {
  const ref = useRef(null)

  useEffect(() => {
    if (!menu) return undefined
    const close = (event) => {
      if (!ref.current?.contains(event.target)) onClose()
    }
    const key = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('mousedown', close)
    window.addEventListener('keydown', key)
    requestAnimationFrame(() => ref.current?.querySelector('button')?.focus())
    return () => {
      window.removeEventListener('mousedown', close)
      window.removeEventListener('keydown', key)
    }
  }, [menu, onClose])

  if (!menu) return null
  const maxX = Math.max(8, window.innerWidth - 184)
  const maxY = Math.max(8, window.innerHeight - 210)

  const run = (callback) => {
    onClose()
    callback(menu.ticket)
  }

  return (
    <div
      ref={ref}
      role="menu"
      aria-label={`Actions for ticket #${menu.ticket.id}`}
      className="fixed z-50 min-w-44 rounded-md border border-border bg-surface p-1 shadow-md"
      style={{ left: Math.min(Math.max(8, menu.x), maxX), top: Math.min(Math.max(8, menu.y), maxY) }}
    >
      <button type="button" role="menuitem" onClick={() => run(onOpen)} className="w-full rounded px-3 py-2 text-left text-sm hover:bg-surface-muted">
        Open ticket
      </button>
      {isCustomer && (
        <button type="button" role="menuitem" onClick={() => run(onArchive)} className="w-full rounded px-3 py-2 text-left text-sm hover:bg-surface-muted">
          {showArchived ? 'Restore from archive' : 'Archive ticket'}
        </button>
      )}
      {isAdmin && (
        <button type="button" role="menuitem" onClick={() => run(onSoftDelete)} className="w-full rounded px-3 py-2 text-left text-sm text-danger hover:bg-danger-muted">
          Delete ticket
        </button>
      )}
      {isAdmin && ['Resolved', 'Closed'].includes(menu.ticket.status) && (
        <button type="button" role="menuitem" onClick={() => run(onHardDelete)} className="w-full rounded px-3 py-2 text-left text-sm font-medium text-danger hover:bg-danger-muted">
          Delete permanently
        </button>
      )}
    </div>
  )
}

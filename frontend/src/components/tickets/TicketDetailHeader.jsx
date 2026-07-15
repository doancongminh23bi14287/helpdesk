import { Link } from 'react-router-dom'
import { ArrowLeftIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { PriorityBadge, Spinner, StatusBadge } from '@/components/ui'
import AiPredictionBadge from '@/components/ai/AiPredictionBadge'
import { cn } from '@/lib/utils'

export function TicketDetailHeader({
  ticket,
  isStaffOrAdmin,
  statusUpdating,
  validNext,
  onStatusChange,
  aiPrediction,
}) {
  const statusControl = isStaffOrAdmin ? (
    <label
      className={cn(
        'relative flex min-h-11 w-full items-center justify-between rounded-md border border-border bg-surface px-3 text-sm font-medium',
        'sm:min-h-9 sm:min-w-36 sm:w-auto',
        statusUpdating && 'opacity-60',
      )}
    >
      <span className="text-xs font-medium text-muted-foreground sm:sr-only">Status</span>
      <span className="ml-auto inline-flex items-center gap-2 sm:ml-0 sm:w-full">
        {statusUpdating ? <Spinner className="h-4 w-4" /> : <StatusBadge status={ticket.status} />}
        <ChevronDownIcon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </span>
      <select
        value=""
        onChange={(event) => event.target.value && onStatusChange(event.target.value)}
        disabled={statusUpdating || validNext.length === 0}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
        aria-label={'Current status ' + ticket.status + '. Change ticket status'}
      >
        <option value="">Change status</option>
        {validNext.map((status) => <option key={status} value={status}>{status}</option>)}
      </select>
    </label>
  ) : (
    <div className="flex min-h-11 w-full items-center justify-between rounded-md border border-border px-3 sm:min-h-0 sm:w-auto sm:border-0 sm:px-0">
      <span className="text-xs font-medium text-muted-foreground sm:sr-only">Status</span>
      <StatusBadge status={ticket.status} />
    </div>
  )

  return (
    <header className="border-b border-border bg-surface px-4 py-3 sm:px-6 sm:py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <Link
          to="/tickets"
          className="inline-flex min-h-9 items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
          Tickets
        </Link>
        <span className="font-mono text-xs text-muted-foreground">#{ticket.id}</span>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {ticket.ticket_type && <span>{ticket.ticket_type}</span>}
            {ticket.source && <span className="capitalize">{ticket.source}</span>}
            {ticket.raised_by_name && <span>• {ticket.raised_by_name}</span>}
            {ticket.service_name && <span>• {ticket.service_name}</span>}
            {ticket.project_name && <span>• {ticket.project_name}</span>}
          </div>
          <h1 className="max-w-4xl break-words text-xl font-semibold leading-7 text-foreground">
            {ticket.subject}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <PriorityBadge priority={ticket.priority} />
            {ticket.assignee_name && (
              <span className="text-xs text-secondary-foreground">Assigned to {ticket.assignee_name}</span>
            )}
            {isStaffOrAdmin && <AiPredictionBadge ticketId={ticket.id} prediction={aiPrediction} />}
          </div>
        </div>
        {statusControl}
      </div>
    </header>
  )
}

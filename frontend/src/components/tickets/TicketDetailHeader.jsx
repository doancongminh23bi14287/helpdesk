import { Link } from 'react-router-dom'
import { ArrowLeftIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { PriorityBadge, Spinner, StatusBadge } from '@/components/ui'
import AiPredictionBadge from '@/components/ai/AiPredictionBadge'
import { cn } from '@/lib/utils'

function getSlaLabel(sla) {
  if (!sla?.state || sla.state === 'unknown') return null
  if (sla.state === 'breached') return 'SLA breached'
  if (sla.state === 'met') return 'SLA met'
  if (typeof sla.hours_remaining !== 'number') return null

  const hours = Math.max(0, sla.hours_remaining)
  if (hours >= 24) return `SLA due in ${Math.round(hours / 24)}d`
  if (hours >= 1) return `SLA due in ${hours.toFixed(hours < 10 && hours % 1 !== 0 ? 1 : 0)}h`
  const minutes = Math.max(1, Math.round(hours * 60))
  return `SLA due in ${minutes}m`
}

function MetadataItem({ children }) {
  return <span className="inline-flex items-center gap-2">{children}</span>
}

export function TicketDetailHeader({
  ticket,
  sla,
  isStaffOrAdmin,
  statusUpdating,
  validNext,
  onStatusChange,
  aiPrediction,
}) {
  const statusControl = isStaffOrAdmin ? (
    <label
      className={cn(
        'relative flex min-h-10 w-full items-center justify-between rounded-md border border-border bg-surface px-3 text-sm font-medium shadow-sm',
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
    <div className="flex min-h-10 w-full items-center justify-between rounded-md border border-border px-3 shadow-sm sm:min-h-0 sm:w-auto sm:border-0 sm:px-0 sm:shadow-none">
      <span className="text-xs font-medium text-muted-foreground sm:sr-only">Status</span>
      <StatusBadge status={ticket.status} />
    </div>
  )

  const slaLabel = getSlaLabel(sla)

  return (
    <header className="border-b border-border bg-surface px-4 py-3 sm:px-6 sm:py-3">
      <div className="mx-auto flex w-full max-w-content flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <Link
            to="/tickets"
            className="inline-flex min-h-9 items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
            Tickets
          </Link>
          <span className="shrink-0 font-mono text-xs text-muted-foreground">#{ticket.id}</span>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between lg:gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-3">
              <h1 className="min-w-0 flex-1 break-words text-xl font-semibold leading-7 text-foreground sm:text-[1.35rem] sm:leading-8">
                {ticket.subject}
              </h1>
              <div className="shrink-0">{statusControl}</div>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] leading-4 text-muted-foreground">
              <MetadataItem><span className="font-medium text-secondary-foreground">#{ticket.id}</span></MetadataItem>
              {ticket.ticket_type && <MetadataItem><span>{ticket.ticket_type}</span></MetadataItem>}
              {ticket.source && <MetadataItem><span className="capitalize">{ticket.source}</span></MetadataItem>}
              <MetadataItem><PriorityBadge priority={ticket.priority} /></MetadataItem>
              {ticket.assignee_name && <MetadataItem><span>Assigned to {ticket.assignee_name}</span></MetadataItem>}
              {isStaffOrAdmin && <MetadataItem><AiPredictionBadge ticketId={ticket.id} prediction={aiPrediction} /></MetadataItem>}
            </div>

            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] leading-4 text-secondary-foreground">
              {ticket.raised_by_name && <MetadataItem><span>{ticket.raised_by_name}</span></MetadataItem>}
              {ticket.service_name && <MetadataItem><span>{ticket.service_name}</span></MetadataItem>}
              {slaLabel && <MetadataItem><span>{slaLabel}</span></MetadataItem>}
              {ticket.project_name && <MetadataItem><span>{ticket.project_name}</span></MetadataItem>}
              {ticket.task_title && <MetadataItem><span>{ticket.task_title}</span></MetadataItem>}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}

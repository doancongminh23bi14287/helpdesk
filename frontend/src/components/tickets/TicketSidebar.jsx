import {
  ChevronDownIcon,
  SparklesIcon,
  UserCircleIcon,
  UserPlusIcon,
} from '@heroicons/react/24/outline'
import { formatDistanceToNow } from 'date-fns'

import ClassifyButton from '@/components/ai/ClassifyButton'
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Select,
  Spinner,
  StatusBadge,
} from '@/components/ui'
import { formatDate, formatDateTime, daysUntil } from '@/lib/utils'
import { parseUTC } from '@/hooks/useRelativeTime'
import { cn } from '@/lib/utils'

function SectionCard({ title, action, children, className }) {
  return (
    <Card className={className}>
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0 px-4 py-3">
        <CardTitle className="text-sm">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0">{children}</CardContent>
    </Card>
  )
}

function InfoRow({ label, value, children }) {
  if (!value && !children) return null
  return (
    <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 border-t border-border py-2.5 first:border-t-0 first:pt-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-right text-xs font-medium text-secondary-foreground">{children || value}</dd>
    </div>
  )
}

function SummaryText({ value }) {
  if (!value) return null
  const lines = value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  return (
    <div className="space-y-2">
      {lines.map((line, index) => {
        const cleaned = line.replace(/^#{1,6}\s*/, '').replace(/\*\*/g, '').replace(/^[-*]\s+/, '')
        const heading = /^#{1,6}\s/.test(line) || /^\*\*.*\*\*:?$/.test(line) || /:$/.test(cleaned)
        return heading
          ? <p key={index} className="text-xs font-semibold text-foreground">{cleaned}</p>
          : <p key={index} className="text-xs leading-5 text-secondary-foreground">{cleaned}</p>
      })}
    </div>
  )
}

function AssignmentCard({
  ticket,
  isStaffOrAdmin,
  isAdmin,
  isStaff,
  user,
  staffList,
  transferReq,
  updating,
  error,
  onAssign,
  onOpenTransfer,
  onAcceptTransfer,
  onDeclineTransfer,
}) {
  if (!isStaffOrAdmin) return null
  const current = ticket.assignees?.length
    ? ticket.assignees
    : ticket.assignee_id
      ? [{ user_id: ticket.assignee_id, full_name: ticket.assignee_name, email: ticket.assignee_email, is_primary: true }]
      : []

  return (
    <SectionCard title="Assignment">
      <div className="space-y-3">
        {current.length > 0 ? (
          <div className="space-y-2">
            {current.map((assignee) => (
              <div key={assignee.user_id} className="flex items-center gap-2 rounded-md bg-surface-muted px-3 py-2">
                <UserCircleIcon className="h-5 w-5 flex-none text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-foreground">{assignee.full_name || assignee.email || `Staff #${assignee.user_id}`}</p>
                  {assignee.email && <p className="truncate text-[11px] text-muted-foreground">{assignee.email}</p>}
                </div>
                {assignee.is_primary && <span className="text-[11px] font-medium text-info">Primary</span>}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-md bg-surface-muted px-3 py-2 text-xs font-medium text-muted-foreground">
            Unassigned
          </div>
        )}

        {isAdmin && (
          <div className="flex items-center gap-2">
            <Select
              value={ticket.assignee_id ?? ''}
              onChange={(event) => onAssign(event.target.value)}
              disabled={updating}
              aria-label="Assign ticket"
              className="flex-1"
            >
              <option value="">Unassigned</option>
              {staffList.map((staff) => (
                <option key={staff.id} value={staff.id}>{staff.full_name || staff.email}</option>
              ))}
            </Select>
            {updating && <Spinner className="h-4 w-4 flex-none" />}
          </div>
        )}

        {error && <p className="text-xs text-danger" role="alert">{error}</p>}

        {isStaff && transferReq?.to_staff_id === user?.id && (
          <div className="space-y-2 rounded-md bg-warning-muted p-3">
            <p className="text-xs text-secondary-foreground">
              {transferReq.from_staff_name} requested a transfer to you.
            </p>
            <div className="flex gap-2">
              <Button type="button" size="sm" onClick={onAcceptTransfer}>Accept</Button>
              <Button type="button" size="sm" variant="outline" onClick={onDeclineTransfer}>Decline</Button>
            </div>
          </div>
        )}

        {isStaff && transferReq?.from_staff_id === user?.id && (
          <p className="rounded-md bg-info-muted px-3 py-2 text-xs text-info">
            Waiting for {transferReq.to_staff_name} to accept the transfer.
          </p>
        )}

        {isStaff && !transferReq && Number(ticket.assignee_id) === Number(user?.id) && (
          <Button type="button" variant="outline" size="sm" className="w-full" onClick={onOpenTransfer}>
            <UserPlusIcon className="h-4 w-4" aria-hidden="true" />
            Request transfer
          </Button>
        )}
      </div>
    </SectionCard>
  )
}

function AiCard({ ticket, predictionSetter, summary, loading, cooldown, onSummarize }) {
  return (
    <SectionCard
      title="AI assistance"
      action={<ClassifyButton ticketId={ticket.id} onClassified={predictionSetter} />}
    >
      <div className="space-y-3">
        {summary?.summary_text ? (
          <div className="rounded-md bg-info-muted/60 p-3">
            <SummaryText value={summary.summary_text} />
            <p className="mt-2 text-[11px] text-muted-foreground">
              Updated {formatDateTime(summary.created_at)} - {summary.summary_count}/10 analyses
            </p>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Generate a concise summary of the issue, missing information and suggested action.</p>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full"
          onClick={onSummarize}
          disabled={loading || cooldown > 0 || (summary?.summary_count ?? 0) >= 10}
          isLoading={loading}
        >
          {!loading && <SparklesIcon className="h-4 w-4" aria-hidden="true" />}
          {cooldown > 0
            ? `Try again in ${cooldown}s`
            : (summary?.summary_count ?? 0) >= 10
              ? 'Analysis limit reached'
              : summary ? 'Analyze again' : 'Analyze ticket'}
        </Button>
      </div>
    </SectionCard>
  )
}

function ActivityCard({ activities }) {
  if (!activities?.length) return null
  const label = (activity) => {
    if (activity.action === 'status_change') return `Status: ${activity.from_value} to ${activity.to_value}`
    if (activity.action === 'priority_change') return `Priority: ${activity.from_value} to ${activity.to_value}`
    if (activity.action === 'auto_assigned') return 'Auto-assigned'
    if (activity.action === 'assigned') return 'Assignment updated'
    if (activity.action === 'replied') return 'Reply added'
    if (activity.action === 'created') return 'Ticket created'
    return activity.action?.replaceAll('_', ' ') || 'Activity'
  }

  return (
    <details className="rounded-lg border border-border bg-surface">
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-foreground focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
        Activity ({activities.length})
      </summary>
      <div className="max-h-72 space-y-3 overflow-y-auto border-t border-border px-4 py-3">
        {activities.map((activity) => (
          <div key={activity.id} className="flex gap-2 text-xs">
            <span className="mt-1.5 h-1.5 w-1.5 flex-none rounded-full bg-border" />
            <span className="flex-1 capitalize text-secondary-foreground">{label(activity)}</span>
            <time className="whitespace-nowrap text-muted-foreground" title={formatDateTime(activity.created_at)}>
              {formatDistanceToNow(parseUTC(activity.created_at), { addSuffix: true })}
            </time>
          </div>
        ))}
      </div>
    </details>
  )
}

function SidebarSections({
  ticket,
  sla,
  activities,
  isStaffOrAdmin,
  isAdmin,
  isStaff,
  user,
  staffList,
  transferReq,
  assignUpdating,
  assignmentError,
  projectActionLoading,
  onAssign,
  onOpenTransfer,
  onAcceptTransfer,
  onDeclineTransfer,
  onCreateProject,
  onOpenLinkProject,
  onUnlinkProject,
  onPredictionChange,
  summary,
  summaryLoading,
  cooldown,
  onSummarize,
}) {
  return (
    <>
      <AssignmentCard
        ticket={ticket}
        isStaffOrAdmin={isStaffOrAdmin}
        isAdmin={isAdmin}
        isStaff={isStaff}
        user={user}
        staffList={staffList}
        transferReq={transferReq}
        updating={assignUpdating}
        error={assignmentError}
        onAssign={onAssign}
        onOpenTransfer={onOpenTransfer}
        onAcceptTransfer={onAcceptTransfer}
        onDeclineTransfer={onDeclineTransfer}
      />
      {isStaffOrAdmin && (
        <AiCard
          ticket={ticket}
          predictionSetter={onPredictionChange}
          summary={summary}
          loading={summaryLoading}
          cooldown={cooldown}
          onSummarize={onSummarize}
        />
      )}
      <ActivityCard activities={activities} />
    </>
  )
}

export function TicketSidebar(props) {
  return (
    <aside aria-label="Ticket information">
      <details className="group lg:hidden">
        <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between rounded-lg border border-border bg-surface px-4 text-sm font-semibold text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          Ticket details
          <ChevronDownIcon className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
        </summary>
        <div className="mt-3 space-y-3">
          <SidebarSections {...props} />
        </div>
      </details>
      <div className="hidden space-y-3 lg:block">
        <SidebarSections {...props} />
      </div>
    </aside>
  )
}

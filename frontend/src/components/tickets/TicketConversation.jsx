import { LockClosedIcon } from '@heroicons/react/24/outline'
import { formatDistanceToNow } from 'date-fns'
import AttachmentList from '@/components/ui/AttachmentList'
import { Card } from '@/components/ui'
import { cn } from '@/lib/utils'
import { TicketBody } from './TicketContent'
import { TicketComposer } from './TicketComposer'

function formatRelative(time) {
  try {
    return formatDistanceToNow(new Date(time), { addSuffix: true })
  } catch {
    return ''
  }
}

function getAuthor(item, ticket) {
  if (item.kind === 'original') {
    return {
      name: item.author_name || item.author_email || 'Customer',
      role: 'Customer',
      tone: 'original',
    }
  }

  const isCustomerReply = Number(item.author_id) === Number(ticket.raised_by)
  return {
    name: item.author_name || item.author_email?.split('@')[0] || item.author_email || 'Unknown author',
    role: item.is_internal ? 'Internal note' : (isCustomerReply ? 'Customer reply' : 'Staff reply'),
    tone: item.is_internal ? 'internal' : (isCustomerReply ? 'customer' : 'staff'),
  }
}

function groupTimelineItems(ticket, replies) {
  const original = {
    id: `ticket-${ticket.id}-original`,
    author_id: ticket.raised_by,
    author_email: ticket.raised_by_email,
    author_name: ticket.raised_by_name || ticket.raised_by_email || 'Customer',
    content: ticket.description || '',
    created_at: ticket.created_at,
    is_internal: false,
    source: 'portal',
    kind: 'original',
  }

  const orderedReplies = [...(replies || [])]
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    .map((reply) => ({ ...reply, kind: 'reply' }))

  const timeline = [original, ...orderedReplies]
  const groups = []

  for (const item of timeline) {
    const author = getAuthor(item, ticket)
    const prev = groups[groups.length - 1]
    const canMerge = prev
      && prev.kind === item.kind
      && prev.authorId === item.author_id
      && prev.isInternal === Boolean(item.is_internal)
      && item.kind !== 'original'

    if (canMerge) {
      prev.items.push(item)
      prev.latestAt = item.created_at
    } else {
      groups.push({
        kind: item.kind,
        authorId: item.author_id,
        author,
        isInternal: Boolean(item.is_internal),
        items: [item],
        latestAt: item.created_at,
      })
    }
  }

  return groups
}

function GroupAvatar({ tone, label }) {
  const styles = {
    customer: 'bg-info text-info-foreground',
    staff: 'bg-primary text-primary-foreground',
    internal: 'bg-warning text-warning-foreground',
    original: 'bg-success text-success-foreground',
  }

  return (
    <div className={cn('flex h-8 w-8 flex-none items-center justify-center rounded-full text-[11px] font-semibold', styles[tone] || styles.staff)}>
      {label.slice(0, 1).toUpperCase()}
    </div>
  )
}

function TimelineGroup({ group, ticket, currentUserId, attachments }) {
  const first = group.items[0]
  const isOriginal = group.kind === 'original'
  const bubbleTone = group.author.tone
  const isCurrentUser = group.authorId != null && currentUserId != null && Number(group.authorId) === Number(currentUserId)
  const bubbleClass = isOriginal
    ? 'bg-info-muted/35'
    : group.isInternal
      ? 'bg-warning-muted/70'
      : bubbleTone === 'customer'
        ? 'bg-surface-muted/35'
        : 'bg-surface'

  return (
    <div className="flex gap-3">
      <div className="relative pt-1">
        <div className="absolute left-4 top-8 bottom-0 w-px bg-border/70" aria-hidden="true" />
        <GroupAvatar tone={bubbleTone} label={group.author.name} />
      </div>

      <div className="min-w-0 flex-1 pb-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="text-sm font-semibold text-foreground">
            {group.author.name}
            {isCurrentUser ? ' (you)' : ''}
          </p>
          <span className="text-[11px] font-medium text-muted-foreground">{group.author.role}</span>
          {group.isInternal && (
            <span className="inline-flex items-center gap-1 rounded-full bg-warning-muted px-2 py-0.5 text-[11px] font-semibold text-warning">
              <LockClosedIcon className="h-3 w-3" aria-hidden="true" />
              Internal note
            </span>
          )}
          <time className="text-[11px] text-muted-foreground" dateTime={first.created_at}>
            {formatRelative(first.created_at)}
          </time>
        </div>

        <div className="mt-1.5 space-y-2">
          {group.items.map((item, index) => {
            const itemAttachments = attachments.filter((attachment) => Number(attachment.reply_id) === Number(item.id))
            return (
              <div
                key={item.id}
                className={cn(
                  'max-w-full rounded-2xl px-4 py-3 text-sm leading-6 text-foreground shadow-sm',
                  bubbleClass,
                  group.items.length > 1 && index > 0 && 'mt-1',
                )}
              >
                {isOriginal && index === 0 && (
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="font-medium text-secondary-foreground">Original request</span>
                    <span>•</span>
                    <span>{first.author_email || 'Customer'}</span>
                  </div>
                )}
                <TicketBody content={item.content} />
                {itemAttachments.length > 0 && <AttachmentList attachments={itemAttachments} />}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export function TicketConversation({
  ticket,
  replies,
  attachments = [],
  currentUserId,
  message,
  onMessageChange,
  isInternal,
  onInternalChange,
  files,
  onAddFiles,
  onRemoveFile,
  onSubmit,
  sending,
  error,
  isStaffOrAdmin,
  isClosed,
}) {
  const timeline = groupTimelineItems(ticket, replies)

  return (
    <Card className="flex h-[calc(100dvh-13rem)] min-h-[36rem] flex-col overflow-hidden lg:h-[calc(100dvh-12rem)]">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
        <div>
          <h2 id="conversation-title" className="section-title">Conversation</h2>
          <p className="mt-1 text-xs text-muted-foreground">Original request and replies in chronological order.</p>
        </div>
        <span className="text-xs text-muted-foreground">{timeline.length} item{timeline.length === 1 ? '' : 's'}</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-5">
        <div className="space-y-4">
          {timeline.map((group) => (
            <TimelineGroup
              key={`${group.kind}-${group.authorId}-${group.latestAt}`}
              group={group}
              ticket={ticket}
              currentUserId={currentUserId}
              attachments={attachments}
            />
          ))}

          {timeline.length === 0 && (
            <div className="rounded-2xl bg-surface-muted/40 px-4 py-5 text-sm text-muted-foreground">
              No conversation yet.
            </div>
          )}
        </div>
      </div>

      <div className="sticky bottom-0 border-t border-border bg-surface/95 px-4 py-4 backdrop-blur sm:px-5">
        {isClosed ? (
          <div className="rounded-2xl bg-surface-muted/60 px-4 py-3 text-center text-sm text-muted-foreground">
            This ticket is closed and no longer accepts replies.
          </div>
        ) : (
          <TicketComposer
            ticketId={ticket.id}
            message={message}
            onMessageChange={onMessageChange}
            isInternal={isInternal}
            onInternalChange={onInternalChange}
            files={files}
            onAddFiles={onAddFiles}
            onRemoveFile={onRemoveFile}
            onSubmit={onSubmit}
            sending={sending}
            error={error}
            isStaffOrAdmin={isStaffOrAdmin}
            embedded
          />
        )}
      </div>
    </Card>
  )
}

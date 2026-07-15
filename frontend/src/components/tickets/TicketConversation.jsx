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

function isCurrentUserMessage(item, currentUserId) {
  return item?.author_id != null && currentUserId != null && Number(item.author_id) === Number(currentUserId)
}

function getAuthorName(item, ticket) {
  if (item.kind === 'original') {
    return item.author_name || item.author_email || 'Customer'
  }
  return item.author_name || item.author_email?.split('@')[0] || item.author_email || 'Unknown author'
}

function getRoleLabel(item, ticket) {
  if (item.kind === 'original') return 'Original request'
  const customerMessage = Number(item.author_id) === Number(ticket.raised_by)
  return item.is_internal ? 'Internal note' : (customerMessage ? 'Customer reply' : 'Staff reply')
}

function bubbleTone(item, ticket) {
  if (item.kind === 'original') return 'original'
  if (item.is_internal) return 'internal'
  return Number(item.author_id) === Number(ticket.raised_by) ? 'customer' : 'staff'
}

function groupTimelineItems(ticket, replies, currentUserId) {
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
    const side = isCurrentUserMessage(item, currentUserId) ? 'right' : 'left'
    const prev = groups[groups.length - 1]
    const mergeable = prev
      && prev.side === side
      && prev.authorId === item.author_id
      && prev.isInternal === Boolean(item.is_internal)
      && item.kind !== 'original'

    if (mergeable) {
      prev.items.push(item)
      prev.latestAt = item.created_at
    } else {
      groups.push({
        side,
        authorId: item.author_id,
        authorName: getAuthorName(item, ticket),
        roleLabel: getRoleLabel(item, ticket),
        isInternal: Boolean(item.is_internal),
        tone: bubbleTone(item, ticket),
        items: [item],
        latestAt: item.created_at,
      })
    }
  }

  return groups
}

function MessageBubble({ item, ticket, currentUserId, attachments, showHeader = true }) {
  const mine = isCurrentUserMessage(item, currentUserId)
  const alignClass = mine ? 'ml-auto' : 'mr-auto'
  const tone = bubbleTone(item, ticket)
  const bubbleClass = tone === 'internal'
    ? 'bg-warning-muted/60 border-warning/20'
    : mine
      ? 'bg-info-muted/35 border-info/15'
      : 'bg-surface border-border/70'
  const name = mine ? 'You' : getAuthorName(item, ticket)
  const role = getRoleLabel(item, ticket)
  const noteIcon = item.is_internal ? (
    <span className="absolute right-2 top-2 inline-flex items-center justify-center rounded-full text-muted-foreground" aria-label="Internal note" title="Internal note">
      <LockClosedIcon className="h-3.5 w-3.5" aria-hidden="true" />
    </span>
  ) : null

  return (
    <div className={cn('flex w-full', mine ? 'justify-end' : 'justify-start')}>
      <div className={cn('w-full max-w-[78%] sm:max-w-[74%]', alignClass)}>
        {showHeader && (
          <div className={cn('mb-1 flex items-center gap-2 text-[11px] text-muted-foreground', mine ? 'justify-end text-right' : 'justify-start text-left')}>
            <span className="font-medium text-secondary-foreground">{name}</span>
            <span>{role}</span>
            <time dateTime={item.created_at}>{formatRelative(item.created_at)}</time>
          </div>
        )}

        <div className={cn('relative rounded-2xl border px-4 py-3 text-sm leading-6 shadow-sm', bubbleClass, noteIcon && 'pr-8')}>
          {noteIcon}
          <TicketBody content={item.content} />
          {attachments.length > 0 && <AttachmentList attachments={attachments} />}
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
  const timeline = groupTimelineItems(ticket, replies, currentUserId)

  return (
    <Card className="flex min-h-[calc(100dvh-9rem)] flex-col overflow-hidden lg:min-h-[680px]">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <h2 id="conversation-title" className="section-title">Conversation</h2>
          <p className="mt-1 text-xs text-muted-foreground">Original request and replies in chronological order.</p>
        </div>
        <span className="text-xs text-muted-foreground">{timeline.length} item{timeline.length === 1 ? '' : 's'}</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-5">
        <div className="space-y-2.5">
          {timeline.map((group) => (
            <div key={`${group.authorId}-${group.latestAt}`} className="space-y-1.5">
              {group.items.map((item, index) => (
                <MessageBubble
                  key={item.id}
                  item={item}
                  ticket={ticket}
                  currentUserId={currentUserId}
                  attachments={attachments.filter((attachment) => Number(attachment.reply_id) === Number(item.id))}
                  showHeader={index === 0}
                />
              ))}
            </div>
          ))}

          {timeline.length === 0 && (
            <div className="rounded-2xl bg-surface-muted/40 px-4 py-5 text-sm text-muted-foreground">
              No conversation yet.
            </div>
          )}
        </div>
      </div>

      <div className="sticky bottom-0 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur sm:px-5">
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

import { LockClosedIcon } from '@heroicons/react/24/outline'
import AttachmentList from '@/components/ui/AttachmentList'
import { Card } from '@/components/ui'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { TicketBody } from './TicketContent'
import { TicketComposer } from './TicketComposer'

function ToneDot({ tone }) {
  const tones = {
    customer: 'bg-info',
    staff: 'bg-primary',
    internal: 'bg-warning',
    original: 'bg-success',
  }
  return <span className={cn('absolute left-5 top-5 h-2.5 w-2.5 rounded-full ring-4 ring-background', tones[tone] || tones.staff)} aria-hidden="true" />
}

function MessageCard({
  tone,
  title,
  subtitle,
  time,
  authorEmail,
  content,
  attachments = [],
  metadata,
  currentUserId,
  authorId,
  original = false,
}) {
  const isCurrentUser = authorId != null && currentUserId != null && Number(authorId) === Number(currentUserId)
  const base = original
    ? 'border-info/30 bg-info-muted/30'
    : tone === 'internal'
      ? 'border-warning/50 bg-warning-muted/60'
      : tone === 'customer'
        ? 'border-info/30 bg-surface'
        : 'border-border bg-surface-muted/40'

  return (
    <article className={cn('relative pl-12', original ? '' : 'pt-1')}>
      <ToneDot tone={tone} />
      <div className={cn('rounded-lg border px-4 py-4 sm:px-5', base)}>
        <div className="flex flex-wrap items-start gap-x-2 gap-y-1">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-foreground" title={authorEmail || undefined}>
                {title}
                {isCurrentUser ? ' (you)' : ''}
              </h3>
              {metadata}
            </div>
            {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          <time className="whitespace-nowrap text-xs text-muted-foreground" dateTime={time}>
            {formatDateTime(time)}
          </time>
        </div>

        <div className="mt-3">
          {content?.trim() && content !== '(attachment)' && <TicketBody content={content} />}
          {attachments.length > 0 && <AttachmentList attachments={attachments} />}
        </div>
      </div>
    </article>
  )
}

function composeRepliesWithOriginal(ticket, replies) {
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

  const orderedReplies = [...(replies || [])].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  return [original, ...orderedReplies.map((reply) => ({ ...reply, kind: 'reply' }))]
}

function TimelineMessage({ item, ticket, currentUserId, attachments }) {
  if (item.kind === 'original') {
    const sender = item.author_name || item.author_email || 'Customer'
    return (
      <MessageCard
        original
        tone="original"
        title={sender}
        subtitle="Original request"
        time={item.created_at}
        authorEmail={item.author_email}
        content={item.content}
        attachments={attachments}
        currentUserId={currentUserId}
        authorId={item.author_id}
      />
    )
  }

  const isCustomerReply = Number(item.author_id) === Number(ticket.raised_by)
  const tone = item.is_internal ? 'internal' : (isCustomerReply ? 'customer' : 'staff')
  const title = item.author_name || item.author_email?.split('@')[0] || item.author_email || 'Unknown author'
  const subtitle = item.is_internal
    ? 'Internal note'
    : isCustomerReply
      ? 'Customer reply'
      : 'Staff reply'

  return (
    <MessageCard
      tone={tone}
      title={title}
      subtitle={subtitle}
      time={item.created_at}
      authorEmail={item.author_email}
      content={item.content}
      attachments={attachments}
      currentUserId={currentUserId}
      authorId={item.author_id}
      metadata={item.is_internal ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-warning-muted px-2 py-0.5 text-[11px] font-semibold text-warning">
          <LockClosedIcon className="h-3 w-3" aria-hidden="true" />
          Internal note
        </span>
      ) : null}
    />
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
  const timeline = composeRepliesWithOriginal(ticket, replies)
  const originalAttachments = attachments.filter((attachment) => !attachment.reply_id)

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-4 py-4 sm:px-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 id="conversation-title" className="section-title">Conversation</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Original request, replies, and notes in chronological order.
            </p>
          </div>
          <span className="text-xs text-muted-foreground">{timeline.length} item{timeline.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      <div className="px-4 py-4 sm:px-5">
        <div className="relative space-y-4 before:absolute before:bottom-0 before:left-5 before:top-0 before:w-px before:bg-border">
          {timeline.map((item) => (
            <TimelineMessage
              key={item.id}
              item={item}
              ticket={ticket}
              currentUserId={currentUserId}
              attachments={item.kind === 'original'
                ? originalAttachments
                : attachments.filter((attachment) => Number(attachment.reply_id) === Number(item.id))}
            />
          ))}

          {timeline.length === 0 && (
            <div className="rounded-lg border border-dashed border-border bg-surface-muted/40 px-4 py-5 text-sm text-muted-foreground">
              No conversation yet.
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-border px-4 py-4 sm:px-5">
        {isClosed ? (
          <div className="rounded-lg border border-dashed border-border bg-surface-muted/60 px-4 py-3 text-center text-sm text-muted-foreground">
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

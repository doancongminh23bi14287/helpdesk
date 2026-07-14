import { LockClosedIcon } from '@heroicons/react/24/outline'
import AttachmentList from '@/components/ui/AttachmentList'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { TicketBody } from './TicketContent'

function TicketMessage({ reply, attachments = [], currentUserId }) {
  const author = reply.author_name || reply.author_email?.split('@')[0] || reply.author_email || 'Unknown author'
  const isCurrentUser = reply.author_id != null && Number(reply.author_id) === Number(currentUserId)
  const initial = author.charAt(0).toUpperCase()

  return (
    <article className={cn('relative pl-11', reply.is_internal && 'rounded-md bg-warning-muted/60 py-3 pr-3')}>
      <div className="absolute left-0 top-0 flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface-muted text-xs font-semibold text-secondary-foreground">
        {initial}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <h3 className="text-sm font-semibold text-foreground" title={reply.author_email || undefined}>
          {author}{isCurrentUser ? ' (you)' : ''}
        </h3>
        {reply.source && <span className="text-xs capitalize text-muted-foreground">{reply.source}</span>}
        {reply.is_internal && (
          <span className="inline-flex items-center gap-1 rounded bg-warning-muted px-1.5 py-0.5 text-[11px] font-medium text-warning">
            <LockClosedIcon className="h-3 w-3" aria-hidden="true" />
            Internal note
          </span>
        )}
        <time className="ml-auto text-xs text-muted-foreground" dateTime={reply.created_at}>
          {formatDateTime(reply.created_at)}
        </time>
      </div>
      <div className="mt-2">
        {reply.content?.trim() && reply.content !== '(attachment)' && <TicketBody content={reply.content} />}
        {attachments.length > 0 && <AttachmentList attachments={attachments} />}
      </div>
    </article>
  )
}

export function TicketConversation({ replies, attachments = [], currentUserId }) {
  return (
    <section aria-labelledby="conversation-title" className="rounded-lg border border-border bg-surface px-4 py-4 sm:px-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 id="conversation-title" className="section-title">Conversation</h2>
        <span className="text-xs text-muted-foreground">{replies.length} repl{replies.length === 1 ? 'y' : 'ies'}</span>
      </div>

      {replies.length === 0 ? (
        <div className="rounded-md border border-dashed border-border bg-surface-muted/50 px-4 py-5 text-center">
          <p className="text-sm font-medium text-foreground">No replies yet</p>
          <p className="mt-1 text-xs text-muted-foreground">Use the composer below to continue the conversation.</p>
        </div>
      ) : (
        <div className="space-y-5">
          {replies.map((reply) => (
            <TicketMessage
              key={reply.id}
              reply={reply}
              currentUserId={currentUserId}
              attachments={attachments.filter((attachment) => Number(attachment.reply_id) === Number(reply.id))}
            />
          ))}
        </div>
      )}
    </section>
  )
}

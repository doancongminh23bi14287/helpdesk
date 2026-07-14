import { PaperClipIcon } from '@heroicons/react/24/outline'
import AttachmentList from '@/components/ui/AttachmentList'
import SafeHtml from '@/components/SafeHtml'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'

function containsHtml(value) {
  return typeof value === 'string' && /<\/?[a-z][\s\S]*>/i.test(value)
}

export function TicketBody({ content, className }) {
  if (!content?.trim()) return <p className="text-sm italic text-muted-foreground">No message content provided.</p>

  if (containsHtml(content)) {
    return <SafeHtml html={content} className={cn('ticket-html-body break-words text-sm leading-6', className)} />
  }

  return (
    <div className={cn('whitespace-pre-wrap break-words text-sm leading-6 text-foreground', className)}>
      {content}
    </div>
  )
}

export function TicketOriginalRequest({ ticket, attachments = [] }) {
  const sender = ticket.raised_by_name || ticket.raised_by_email || 'Customer'
  const initial = sender.charAt(0).toUpperCase()

  return (
    <section aria-labelledby="original-request-title" className="rounded-lg border border-border bg-surface">
      <header className="flex items-start gap-3 border-b border-border px-4 py-3 sm:px-5">
        <div className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-info-muted text-sm font-semibold text-info">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <h2 id="original-request-title" className="text-sm font-semibold text-foreground">Original request</h2>
          <p className="truncate text-xs text-muted-foreground" title={ticket.raised_by_email || undefined}>
            {sender}
          </p>
        </div>
        <time className="whitespace-nowrap text-xs text-muted-foreground" dateTime={ticket.created_at}>
          {formatDateTime(ticket.created_at)}
        </time>
      </header>

      <div className="px-4 py-4 sm:px-5">
        <p className="mb-3 text-sm font-semibold text-foreground">{ticket.subject}</p>
        <TicketBody content={ticket.description || ''} />
        {attachments.length > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <p className="flex items-center gap-1.5 text-xs font-medium text-secondary-foreground">
              <PaperClipIcon className="h-4 w-4" aria-hidden="true" />
              {attachments.length} attachment{attachments.length !== 1 ? 's' : ''}
            </p>
            <AttachmentList attachments={attachments} />
          </div>
        )}
      </div>
    </section>
  )
}

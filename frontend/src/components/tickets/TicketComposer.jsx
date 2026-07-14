import { useRef } from 'react'
import {
  LockClosedIcon,
  PaperAirplaneIcon,
  PaperClipIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import AiReplyDraft from '@/components/ai/AiReplyDraft'
import { Button, ErrorState, Textarea } from '@/components/ui'

const ACCEPTED_FILES = 'image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv'

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

export function TicketComposer({
  ticketId,
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
}) {
  const inputRef = useRef(null)
  const formRef = useRef(null)
  const canSend = Boolean(message.trim() || files.length)

  return (
    <section aria-labelledby="reply-composer-title" className="rounded-lg border border-border bg-surface">
      <div className="space-y-3 border-b border-border px-4 py-3 sm:flex sm:items-center sm:justify-between sm:space-y-0 sm:px-5">
        <div>
          <h2 id="reply-composer-title" className="text-sm font-semibold text-foreground">
            {isInternal ? 'Add internal note' : 'Reply to customer'}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {isInternal ? 'Only staff and administrators can see this note.' : 'This message will be visible to the customer.'}
          </p>
        </div>

        {isStaffOrAdmin && (
          <div className="flex w-full rounded-md border border-border bg-surface-muted p-1 sm:inline-flex sm:w-auto" role="group" aria-label="Message visibility">
            <button
              type="button"
              onClick={() => onInternalChange(false)}
              aria-pressed={!isInternal}
              className={
                'min-h-9 flex-1 rounded px-3 py-1.5 text-xs font-medium transition sm:flex-none ' +
                (!isInternal ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')
              }
            >
              Public reply
            </button>
            <button
              type="button"
              onClick={() => onInternalChange(true)}
              aria-label="Internal note"
              aria-pressed={isInternal}
              className={
                'inline-flex min-h-9 flex-1 items-center justify-center gap-1 rounded px-3 py-1.5 text-xs font-medium transition sm:flex-none ' +
                (isInternal ? 'bg-warning-muted text-warning shadow-sm' : 'text-muted-foreground hover:text-foreground')
              }
            >
              <LockClosedIcon className="h-3.5 w-3.5" aria-hidden="true" />
              Internal
            </button>
          </div>
        )}
      </div>

      <form ref={formRef} onSubmit={onSubmit} className="space-y-3 px-4 py-4 sm:px-5">
        {isStaffOrAdmin && <AiReplyDraft ticketId={ticketId} onUseDraft={onMessageChange} />}

        <Textarea
          id="ticket-reply"
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === 'Enter'
              && !event.shiftKey
              && !event.nativeEvent.isComposing
              && !sending
            ) {
              event.preventDefault()
              if (canSend) formRef.current?.requestSubmit()
            }
          }}
          placeholder={isInternal ? 'Write an internal note...' : 'Write a reply...'}
          rows={5}
          aria-label={isInternal ? 'Internal note' : 'Public reply'}
        />

        {files.length > 0 && (
          <div className="flex flex-wrap gap-2" aria-label="Selected attachments">
            {files.map((file) => (
              <span key={file.name} className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-border bg-surface-muted px-2 py-1 text-xs text-secondary-foreground">
                <PaperClipIcon className="h-3.5 w-3.5 flex-none" aria-hidden="true" />
                <span className="max-w-48 truncate" title={file.name}>{file.name}</span>
                <span className="text-muted-foreground">{formatFileSize(file.size)}</span>
                <button
                  type="button"
                  onClick={() => onRemoveFile(file.name)}
                  className="rounded p-0.5 text-muted-foreground hover:text-danger"
                  aria-label={'Remove ' + file.name}
                >
                  <XMarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </span>
            ))}
          </div>
        )}

        {error && <ErrorState title="Message was not sent" description={error} />}

        <input
          ref={inputRef}
          type="file"
          multiple
          className="sr-only"
          accept={ACCEPTED_FILES}
          aria-label="Attach files to reply"
          onChange={(event) => {
            onAddFiles(Array.from(event.target.files || []))
            event.target.value = ''
          }}
        />

        <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2 sm:flex">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-h-11 sm:min-h-0"
            onClick={() => inputRef.current?.click()}
          >
            <PaperClipIcon className="h-4 w-4" aria-hidden="true" />
            Attach
          </Button>
          <span className="hidden text-xs text-muted-foreground sm:inline">Enter to send, Shift+Enter for a new line</span>
          <Button
            type="submit"
            className="min-h-11 w-full sm:ml-auto sm:min-h-0 sm:w-auto"
            disabled={!canSend || sending}
            isLoading={sending}
          >
            {!sending && <PaperAirplaneIcon className="h-4 w-4" aria-hidden="true" />}
            {isInternal ? 'Add note' : 'Send reply'}
          </Button>
        </div>
      </form>
    </section>
  )
}

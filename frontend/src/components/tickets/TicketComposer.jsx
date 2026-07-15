import { useRef } from 'react'
import {
  LockClosedIcon,
  PaperAirplaneIcon,
  PaperClipIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import AiReplyDraft from '@/components/ai/AiReplyDraft'
import { Button, ErrorState, Textarea } from '@/components/ui'
import { cn } from '@/lib/utils'

const ACCEPTED_FILES = 'image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv'

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function ToggleButton({ active, onClick, children, icon, ariaLabel }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      aria-pressed={active}
      className={cn(
        'inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors',
        active
          ? 'bg-surface text-foreground shadow-sm'
          : 'text-muted-foreground hover:bg-surface-muted hover:text-foreground',
      )}
    >
      {icon}
      <span>{children}</span>
    </button>
  )
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
  embedded = false,
}) {
  const inputRef = useRef(null)
  const formRef = useRef(null)
  const canSend = Boolean(message.trim() || files.length)

  return (
    <section
      aria-labelledby="reply-composer-title"
      className={cn(
        'rounded-2xl border border-border bg-surface shadow-sm',
        embedded ? 'shadow-none' : '',
      )}
    >
      <form
        ref={formRef}
        onSubmit={onSubmit}
        className={cn('space-y-3', embedded ? 'p-3 sm:p-4' : 'px-4 py-4 sm:px-5')}
      >
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
          placeholder={isInternal ? 'Write an internal note…' : 'Write a reply…'}
          rows={embedded ? 4 : 5}
          className="min-h-[7rem] resize-none border-border bg-background text-sm leading-6"
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

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-9 px-3"
            onClick={() => inputRef.current?.click()}
            aria-label="Attach files"
            title="Attach files"
          >
            <PaperClipIcon className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline">Attach</span>
          </Button>

          {isStaffOrAdmin && (
            <div className="inline-flex rounded-md border border-border bg-surface-muted p-1">
              <ToggleButton
                active={!isInternal}
                onClick={() => onInternalChange(false)}
                ariaLabel="Public reply"
              >
                Public
              </ToggleButton>
              <ToggleButton
                active={isInternal}
                onClick={() => onInternalChange(true)}
                ariaLabel="Internal note"
                icon={<LockClosedIcon className="h-3.5 w-3.5" aria-hidden="true" />}
              >
                Internal
              </ToggleButton>
            </div>
          )}

          {isStaffOrAdmin && <AiReplyDraft ticketId={ticketId} onUseDraft={onMessageChange} compact />}

          <span className="hidden text-[11px] text-muted-foreground md:inline" title="Enter to send, Shift+Enter for a new line">
            Enter to send
          </span>

          <Button
            type="submit"
            className="ml-auto h-9 px-4"
            disabled={!canSend || sending}
            isLoading={sending}
            title="Enter to send, Shift+Enter for a new line"
          >
            {!sending && <PaperAirplaneIcon className="h-4 w-4" aria-hidden="true" />}
            Send
          </Button>
        </div>
      </form>
    </section>
  )
}

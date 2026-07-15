import { useState } from 'react'
import { useRole } from '@/hooks/useRole'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { Spinner } from '@/components/ui'
import client from '@/api/client'
import { SparklesIcon, XMarkIcon } from '@heroicons/react/24/outline'

export default function AiReplyDraft({ ticketId, onUseDraft, compact = false }) {
  const { isStaff, isAdmin } = useRole()
  const addToast = useNotificationStore((s) => s.addToast)
  const [loading, setLoading] = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [visible, setVisible] = useState(false)

  if (!isStaff && !isAdmin) return null

  async function handleGenerate() {
    setLoading(true)
    setSuggestion(null)
    setVisible(false)
    try {
      const r = await client.post(`/ai/tickets/${ticketId}/suggest-reply`)
      setSuggestion(r.data)
      setVisible(true)
    } catch {
      addToast({ type: 'error', message: 'Không thể tạo gợi ý AI' })
    } finally {
      setLoading(false)
    }
  }

  function handleUse() {
    if (!suggestion) return
    onUseDraft?.(suggestion.generated_text)
    client.patch(`/ai/suggestions/${suggestion.id}/accept`, {}).catch(() => {})
    setVisible(false)
    setSuggestion(null)
  }

  function handleDismiss() {
    setVisible(false)
    setSuggestion(null)
  }

  const panel = visible && suggestion ? (
    <div className={compact ? 'absolute right-0 top-full z-30 mt-2 w-[min(28rem,calc(100vw-2rem))]' : 'mt-2'}>
      <div className="overflow-hidden rounded-lg border border-info/20 bg-surface shadow-lg">
        <div className="flex items-center justify-between gap-2 border-b border-info/20 bg-info-muted/50 px-3 py-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-info">
            <SparklesIcon className="h-3.5 w-3.5" />
            AI draft
          </div>
          <button type="button" onClick={handleDismiss} className="rounded p-0.5 text-muted-foreground hover:text-foreground" aria-label="Close AI draft preview">
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="px-3 py-2">
          <textarea
            readOnly
            value={suggestion.generated_text}
            rows={4}
            className="w-full resize-none bg-transparent text-sm leading-6 text-foreground outline-none"
          />
        </div>
        <div className="flex items-center gap-2 border-t border-border px-3 py-2">
          <button
            type="button"
            onClick={handleUse}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary-hover"
          >
            Use
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            className="inline-flex items-center rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-secondary-foreground hover:bg-surface-muted hover:text-foreground"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  ) : null

  const button = (
    <button
      type="button"
      onClick={handleGenerate}
      disabled={loading}
      aria-label="Generate AI draft"
      className="inline-flex h-9 items-center gap-1.5 rounded-md border border-info/20 bg-info-muted px-3 text-xs font-medium text-info transition-colors hover:bg-info-muted/80 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {loading ? <Spinner className="h-3.5 w-3.5" /> : <SparklesIcon className="h-3.5 w-3.5" />}
      AI Draft
    </button>
  )

  if (compact) {
    return <div className="relative inline-flex">{button}{panel}</div>
  }

  return (
    <div className="mb-2 relative">
      {button}
      {panel}
    </div>
  )
}

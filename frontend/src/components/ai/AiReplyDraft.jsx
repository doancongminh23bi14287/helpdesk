import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useRole } from '@/hooks/useRole'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { Spinner } from '@/components/ui'
import client from '@/api/client'
import { SparklesIcon } from '@heroicons/react/24/outline'

export default function AiReplyDraft({ ticketId, onUseDraft, compact = false }) {
  const { isStaff, isAdmin } = useRole()
  const addToast = useNotificationStore((s) => s.addToast)
  const [loading, setLoading] = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [visible, setVisible] = useState(false)
  const [panelStyle, setPanelStyle] = useState(null)
  const buttonRef = useRef(null)

  useLayoutEffect(() => {
    if (!visible || !suggestion || !compact) return undefined

    const updatePosition = () => {
      const button = buttonRef.current
      if (!button) return
      const composer = button.closest('form')
      const anchorRect = (composer || button).getBoundingClientRect()
      const viewportWidth = window.innerWidth
      const horizontalInset = 12
      const width = Math.min(480, viewportWidth - horizontalInset * 2, anchorRect.width)
      const halfWidth = width / 2
      const preferredCenter = anchorRect.left + anchorRect.width / 2
      const left = Math.min(
        Math.max(preferredCenter, horizontalInset + halfWidth),
        viewportWidth - horizontalInset - halfWidth,
      )

      setPanelStyle({
        bottom: Math.max(12, window.innerHeight - anchorRect.top + 12),
        left,
        maxHeight: Math.max(160, Math.min(360, anchorRect.top - 24)),
        width,
      })
    }

    updatePosition()
    window.addEventListener('resize', updatePosition)
    document.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      document.removeEventListener('scroll', updatePosition, true)
    }
  }, [compact, suggestion, visible])

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

  const panelCard = visible && suggestion ? (
    <div className='flex max-h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface text-foreground shadow-md'>
      <div className='flex shrink-0 items-center gap-2 border-b border-border bg-info-muted/50 px-4 py-3'>
        <SparklesIcon className='h-4 w-4 text-info' aria-hidden='true' />
        <span className='text-sm font-semibold'>AI Draft</span>
      </div>
      <div className='min-h-0 flex-1 overflow-y-auto px-4 py-3'>
        <p className='whitespace-pre-wrap break-words text-sm leading-6 text-foreground'>
          {suggestion.generated_text}
        </p>
      </div>
      <div className='flex shrink-0 items-center justify-between gap-3 border-t border-border px-4 py-3'>
        <button
          type='button'
          onClick={handleDismiss}
          className='inline-flex min-h-10 items-center rounded-lg px-3 text-sm font-medium text-secondary-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
        >
          Close
        </button>
        <button
          type='button'
          onClick={handleUse}
          className='inline-flex min-h-10 items-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
        >
          Accept Draft
        </button>
      </div>
    </div>
  ) : null

  const panel = panelCard && compact && panelStyle && typeof document !== 'undefined'
    ? createPortal(
      <div
        className='fixed z-[100] -translate-x-1/2'
        style={panelStyle}
        role='dialog'
        aria-label='AI suggested reply'
      >
        {panelCard}
      </div>,
      document.body,
    )
    : panelCard ? (
      <div className='mb-3 w-full max-w-[30rem]'>
        {panelCard}
      </div>
    ) : null

  const button = (
    <button
      ref={buttonRef}
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

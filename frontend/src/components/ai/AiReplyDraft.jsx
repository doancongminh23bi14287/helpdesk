import { useState } from 'react'
import { useRole } from '@/hooks/useRole'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { Spinner } from '@/components/ui'
import client from '@/api/client'
import { SparklesIcon, XMarkIcon } from '@heroicons/react/24/outline'

export default function AiReplyDraft({ ticketId, onUseDraft }) {
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

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={handleGenerate}
        disabled={loading}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-teal-200 text-teal-700 bg-teal-50 hover:bg-teal-100 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Spinner className="w-3 h-3" />
            Đang tạo…
          </>
        ) : (
          <>
            <SparklesIcon className="w-3.5 h-3.5" />
            Soạn thảo AI
          </>
        )}
      </button>

      {visible && suggestion && (
        <div
          className="mt-2 border border-teal-200 rounded-lg bg-teal-50/60 overflow-hidden"
          style={{ animation: 'fadeIn 0.15s ease-out' }}
        >
          <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}`}</style>
          <div className="flex items-center justify-between px-3 py-2 border-b border-teal-200 bg-teal-50">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-teal-800">
              <SparklesIcon className="w-3.5 h-3.5" />
              Gợi ý AI
              <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-700 text-[10px] font-medium">Xem trước</span>
            </div>
            <button type="button" onClick={handleDismiss} className="text-teal-400 hover:text-teal-700">
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="px-3 py-2">
            <textarea
              readOnly
              value={suggestion.generated_text}
              rows={4}
              className="w-full text-sm text-gray-700 bg-transparent resize-none outline-none leading-relaxed"
            />
          </div>
          <div className="flex items-center gap-2 px-3 pb-3">
            <button
              type="button"
              onClick={handleUse}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-teal-600 text-white text-xs font-semibold hover:bg-teal-700 transition-colors"
            >
              Dùng bản này
            </button>
            <button
              type="button"
              onClick={handleDismiss}
              className="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 text-xs font-medium hover:bg-gray-50 transition-colors"
            >
              Bỏ qua
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

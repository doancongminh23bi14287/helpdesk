import { useState } from 'react'
import { useRole } from '@/hooks/useRole'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { Spinner } from '@/components/ui'
import client from '@/api/client'
import { SparklesIcon } from '@heroicons/react/24/outline'

export default function ClassifyButton({ ticketId, onClassified }) {
  const { isStaff, isAdmin } = useRole()
  const addToast = useNotificationStore((s) => s.addToast)
  const [loading, setLoading] = useState(false)

  if (!isStaff && !isAdmin) return null

  async function handleClick() {
    setLoading(true)
    try {
      const r = await client.post(`/ai/tickets/${ticketId}/classify`)
      onClassified?.(r.data)
    } catch {
      addToast({ type: 'error', message: 'AI không phản hồi, thử lại sau' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-teal-200 text-teal-700 bg-teal-50 hover:bg-teal-100 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? <Spinner className="w-3 h-3" /> : <SparklesIcon className="w-3.5 h-3.5" />}
      Phân tích AI
    </button>
  )
}

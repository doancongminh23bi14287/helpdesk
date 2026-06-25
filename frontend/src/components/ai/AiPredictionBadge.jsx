import { useState, useEffect } from 'react'
import { useRole } from '@/hooks/useRole'
import client from '@/api/client'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'

export default function AiPredictionBadge({ ticketId, prediction: externalPrediction }) {
  const { isStaff, isAdmin } = useRole()
  const [prediction, setPrediction] = useState(externalPrediction ?? null)
  const [loading, setLoading] = useState(!externalPrediction)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (externalPrediction) {
      setPrediction(externalPrediction)
      setLoading(false)
      return
    }
    if (!ticketId) return
    setLoading(true)
    client.get(`/ai/tickets/${ticketId}/prediction`)
      .then((r) => setPrediction(r.data))
      .catch(() => setPrediction(null))
      .finally(() => setLoading(false))
  }, [ticketId, externalPrediction])

  if (!isStaff && !isAdmin) return null
  if (loading) return <span className="inline-block w-14 h-4 rounded bg-gray-100 animate-pulse" />
  if (!prediction) return null

  const pct = prediction.confidence != null ? Math.round(prediction.confidence * 100) : null
  const lowConfidence = pct != null && pct < 60

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-teal-50 text-teal-700 border border-teal-200 hover:bg-teal-100 transition-colors"
        title="AI prediction"
      >
        <span>AI</span>
        {lowConfidence && <ExclamationTriangleIcon className="w-2.5 h-2.5 text-amber-500" />}
      </button>
      {expanded && (
        <div className="absolute left-0 top-full mt-1 z-20 bg-white border border-gray-200 rounded-lg shadow-md p-2.5 text-xs text-gray-700 whitespace-nowrap min-w-[200px]">
          <p className="font-semibold text-gray-900 mb-1">AI dự đoán</p>
          <p>Danh mục: <span className="font-medium">{prediction.predicted_category}</span></p>
          <p>Ưu tiên: <span className="font-medium">{prediction.predicted_priority}</span></p>
          {pct != null && (
            <p className={lowConfidence ? 'text-amber-600' : 'text-gray-600'}>
              Độ tin cậy: {pct}%
              {lowConfidence && ' ⚠ thấp'}
            </p>
          )}
          <button
            type="button"
            onClick={() => setExpanded(false)}
            className="mt-1 text-gray-400 hover:text-gray-600"
          >
            Đóng
          </button>
        </div>
      )}
    </span>
  )
}

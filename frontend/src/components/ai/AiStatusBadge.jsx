import { useState, useEffect } from 'react'
import { useRole } from '@/hooks/useRole'
import client from '@/api/client'

let _cachedHealth = null
let _cacheTime = 0
const CACHE_MS = 5 * 60 * 1000

export default function AiStatusBadge() {
  const { isAdmin } = useRole()
  const [health, setHealth] = useState(_cachedHealth)

  useEffect(() => {
    if (!isAdmin) return
    const now = Date.now()
    if (_cachedHealth && now - _cacheTime < CACHE_MS) {
      setHealth(_cachedHealth)
      return
    }
    client.get('/ai/health')
      .then((r) => {
        _cachedHealth = r.data
        _cacheTime = Date.now()
        setHealth(r.data)
      })
      .catch(() => {})
  }, [isAdmin])

  if (!isAdmin || !health) return null

  const active = health.ai_enabled && health.groq_configured
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
        active ? 'bg-teal-50 text-teal-700 border border-teal-200' : 'bg-gray-100 text-gray-500 border border-gray-200'
      }`}
      title={active ? `AI active · model: ${health.model}` : 'AI inactive'}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-teal-500' : 'bg-gray-400'}`} />
      {active ? 'AI Active' : 'AI Inactive'}
    </span>
  )
}

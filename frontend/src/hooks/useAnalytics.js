import { useState, useEffect } from 'react'
import { getTicketAnalytics } from '@/services/api'

export function useAnalytics() {
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getTicketAnalytics()
      .then(setAnalytics)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return { analytics, loading, error }
}

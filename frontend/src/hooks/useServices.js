import { useState, useEffect, useCallback } from 'react'
import { getCustomerServices } from '@/services/api'

export function useServices() {
  const [services, setServices] = useState({ hosting: [], subscriptions: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(() => {
    setLoading(true)
    getCustomerServices()
      .then((data) => {
        const normalized = data ?? { customer: null, hosting: [], subscriptions: [] }
        setServices({
          customer: normalized.customer ?? null,
          hosting: Array.isArray(normalized.hosting) ? normalized.hosting : [],
          subscriptions: Array.isArray(normalized.subscriptions) ? normalized.subscriptions : [],
        })
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetch() }, [fetch])

  return { services, loading, error, refetch: fetch }
}

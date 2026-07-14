import { useCallback, useEffect, useMemo, useState } from 'react'
import { getMySubscriptions, listSubscriptions } from '@/api/subscriptions'
import { useAuthStore } from '@/hooks/useAuth'

export function useSubscriptions(filters = {}) {
  const user = useAuthStore((state) => state.user)
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [requestVersion, setRequestVersion] = useState(0)
  const filterKey = useMemo(() => JSON.stringify(filters), [filters])

  const refetch = useCallback(() => setRequestVersion((value) => value + 1), [])

  useEffect(() => {
    let cancelled = false
    const params = JSON.parse(filterKey)

    setLoading(true)
    setError(null)
    const request = user?.role === 'customer'
      ? getMySubscriptions()
      : listSubscriptions({ ...params, per_page: 100 })

    request
      .then((response) => {
        if (cancelled) return
        const items = Array.isArray(response) ? response : response?.items
        const filtered = user?.role === 'customer' && params.status
          ? (items ?? []).filter((item) => item.status === params.status)
          : (items ?? [])
        setData(filtered)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err.message || 'Unable to load subscriptions')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [filterKey, requestVersion, user?.role])

  return { data, loading, error, refetch }
}

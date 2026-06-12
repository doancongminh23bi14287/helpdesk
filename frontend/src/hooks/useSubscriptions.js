import { useState, useEffect } from 'react'
import { erpClient } from '@/erp'

export function useSubscriptions(filters = {}) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    erpClient.subscription.list(filters)
      .then(res => { if (!cancelled) setData(res.data ?? []) })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(()  => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [JSON.stringify(filters)]) // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error }
}

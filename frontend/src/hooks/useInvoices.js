import { useEffect, useState } from 'react'
import { listInvoices, listMyInvoices } from '@/api/invoices'
import { useAuthStore } from '@/hooks/useAuth'

export function useInvoices(subscriptionId = null) {
  const user = useAuthStore((state) => state.user)
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const request = user?.role === 'customer'
      ? listMyInvoices()
      : listInvoices({ per_page: 100 })

    request
      .then((response) => {
        if (cancelled) return
        const items = Array.isArray(response) ? response : response?.items
        setData(
          subscriptionId == null
            ? (items ?? [])
            : (items ?? []).filter((invoice) => invoice.subscription_id === Number(subscriptionId)),
        )
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err.message || 'Unable to load invoices')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [subscriptionId, user?.role])

  return { data, loading, error }
}

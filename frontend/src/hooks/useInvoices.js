import { useState, useEffect } from 'react'
import { erpClient, erpGet } from '@/erp'

// Same fields the InvoicesTab renders
const INVOICE_FIELDS = JSON.stringify([
  'name', 'status', 'customer', 'grand_total', 'outstanding_amount', 'due_date', 'subscription',
])

export function useInvoices(subscriptionName = null) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    // When a subscriptionName is given, fetch only invoices for that subscription.
    // Otherwise fetch all invoices without a subscription filter (preserves old behaviour).
    const request = subscriptionName
      ? erpClient.subscription.getInvoices(subscriptionName)
      : erpGet('/Sales%20Invoice', { fields: INVOICE_FIELDS, limit: 50, order_by: 'modified desc' })

    request
      .then(res => { if (!cancelled) setData(res.data ?? []) })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(()  => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [subscriptionName])

  return { data, loading, error }
}

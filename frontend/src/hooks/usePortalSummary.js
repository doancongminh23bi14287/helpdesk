import { useState, useEffect, useCallback } from 'react'
import { getPortalSummary } from '@/api/tickets'

/**
 * Fetch aggregated dashboard stats from the backend in a single call.
 * Uses get_portal_summary which counts directly from raw SQL —
 * immune to HD Ticket role-permission issues that break frappe.get_all().
 *
 * @returns {{
 *   summary: {open_tickets, resolved_tickets, services_count, total_orders} | null,
 *   loading: boolean,
 *   refetch: Function
 * }}
 */
export function usePortalSummary() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getPortalSummary()
      setSummary(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  return { summary, loading, refetch: fetch }
}

import { useState, useEffect, useCallback } from 'react'
import {
  getTickets,
  getTicket,
  getSla,
  createTicket,
  replyToTicket,
} from '@/api/tickets'

/**
 * Fetch the current user's ticket list.
 * @returns {{ tickets: Array, loading: boolean, error: string|null, refetch: Function }}
 */
export function useTickets() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getTickets()
      setTickets(data.items ?? [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  return { tickets, loading, error, refetch: fetch }
}

/**
 * Fetch a single ticket, its replies, activities, and SLA status.
 * Uses AbortController to cancel in-flight requests when ticketId changes
 * or the component unmounts, preventing stale-state race conditions.
 *
 * @param {string|number} ticketId
 * @returns {{ ticket, comments, activities, sla, loading, error, reply, refetch }}
 */
export function useTicket(ticketId) {
  const [ticket, setTicket] = useState(null)
  const [comments, setComments] = useState([])
  const [activities, setActivities] = useState([])
  const [sla, setSla] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [rev, setRev] = useState(0)

  useEffect(() => {
    if (!ticketId) return
    const controller = new AbortController()
    const { signal } = controller
    setLoading(true)
    setError(null)

    Promise.all([
      getTicket(ticketId, { signal }),
      getSla(ticketId, { signal }).catch(() => null),
    ])
      .then(([ticketData, slaData]) => {
        if (signal.aborted) return
        setTicket(ticketData)
        setComments(ticketData?.replies ?? [])
        setActivities(ticketData?.activities ?? [])
        setSla(slaData)
        setLoading(false)
      })
      .catch((e) => {
        if (signal.aborted) return
        setError(e.message)
        setLoading(false)
      })

    return () => controller.abort()
  }, [ticketId, rev])

  const refetch = useCallback(() => setRev(r => r + 1), [])

  const appendReply = useCallback((newReply) => {
    setComments(prev =>
      prev.some(r => r.id === newReply.id) ? prev : [...prev, newReply]
    )
  }, [])

  const silentRefetch = useCallback(() => {
    if (!ticketId) return
    Promise.all([
      getTicket(ticketId),
      getSla(ticketId).catch(() => null),
    ]).then(([ticketData, slaData]) => {
      setTicket(ticketData)
      setComments(ticketData?.replies ?? [])
      setActivities(ticketData?.activities ?? [])
      if (slaData) setSla(slaData)
    }).catch(() => {})
  }, [ticketId])

  const reply = useCallback(async (content, isInternal = false) => {
    return await replyToTicket(ticketId, content, isInternal)
  }, [ticketId])

  return { ticket, comments, activities, sla, loading, error, reply, refetch, appendReply, silentRefetch }
}

/**
 * Submit a new ticket.
 * @returns {{ submit: Function, loading: boolean, error: string|null }}
 */
export function useCreateTicket() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const submit = useCallback(async (data) => {
    setLoading(true)
    setError(null)
    try {
      return await createTicket(data)
    } catch (e) {
      const msg = e.message || 'Failed to create ticket'
      setError(msg)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  return { submit, loading, error }
}

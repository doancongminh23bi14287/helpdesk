import { useState, useEffect } from 'react'
import { formatDistanceToNow } from 'date-fns'

// Backend returns UTC timestamps without 'Z'. Safe with string | Date | number | null.
export function parseUTC(value) {
  if (value == null) return new Date(NaN)
  if (value instanceof Date) return value
  if (typeof value === 'number') return new Date(value)
  if (typeof value !== 'string') return new Date(value)
  const s = value.trim()
  if (!s) return new Date(NaN)
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(s)
  const iso = hasTz ? s : s.replace(' ', 'T') + 'Z'
  return new Date(iso)
}

function calcRelative(dateStr) {
  if (!dateStr) return ''
  const d = parseUTC(dateStr)
  if (isNaN(d.getTime())) return ''
  return formatDistanceToNow(d, { addSuffix: true })
}

export function useRelativeTime(dateStr) {
  const [label, setLabel] = useState(() => calcRelative(dateStr))

  useEffect(() => {
    setLabel(calcRelative(dateStr))
    const id = setInterval(() => setLabel(calcRelative(dateStr)), 60_000)
    return () => clearInterval(id)
  }, [dateStr])

  return label
}

export function normalizeTrendData(rows) {
  if (!Array.isArray(rows)) return []

  return rows
    .map((row) => {
      const date = typeof row?.date === 'string' ? row.date.trim() : ''
      const parsedValue = Number(row?.value ?? row?.v)

      if (!date) return null

      return {
        date,
        value: Number.isFinite(parsedValue) ? parsedValue : 0,
      }
    })
    .filter(Boolean)
    .sort((a, b) => a.date.localeCompare(b.date))
}

function toLocalDateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function fillDailyTrend(rows, { days = 30, endDate = new Date() } = {}) {
  const normalized = normalizeTrendData(rows)
  if (normalized.length === 0 || days < 1) return []

  const valuesByDate = new Map(normalized.map(({ date, value }) => [date, value]))
  const rangeEnd = new Date(endDate)
  rangeEnd.setHours(12, 0, 0, 0)

  return Array.from({ length: days }, (_, index) => {
    const date = new Date(rangeEnd)
    date.setDate(rangeEnd.getDate() - (days - 1 - index))
    const dateKey = toLocalDateKey(date)

    return {
      date: dateKey,
      value: valuesByDate.get(dateKey) ?? 0,
    }
  })
}

export function getTrendDomain(rows) {
  const values = rows.map(({ value }) => value)
  if (values.length === 0) return [0, 1]

  const minimum = Math.min(...values)
  const maximum = Math.max(...values)

  if (minimum === maximum) {
    const padding = maximum === 0 ? 1 : Math.max(Math.abs(maximum) * 0.1, 1)
    return [minimum - padding, maximum + padding]
  }

  const padding = (maximum - minimum) * 0.12
  return [Math.max(0, minimum - padding), maximum + padding]
}

export function getTrendState(rows, { isLoading = false, error = null } = {}) {
  if (isLoading) return 'loading'
  if (error) return 'error'
  if (rows.length === 0) return 'empty'
  if (rows.length === 1) return 'single'
  return 'ready'
}
